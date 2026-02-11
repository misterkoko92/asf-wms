import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect

from contacts.models import Contact

from .import_services import apply_pallet_listing_import
from .import_utils import (
    extract_tabular_data,
    get_pdf_page_count,
    list_excel_sheets,
    parse_int,
)
from .pallet_listing import (
    PALLET_LISTING_REQUIRED_FIELDS,
    PALLET_LOCATION_FIELDS,
    PALLET_REVIEW_FIELDS,
    apply_listing_mapping,
    build_listing_columns,
    build_listing_extract_options,
    build_listing_mapping_defaults,
    build_listing_review_rows,
    load_listing_table,
)
from .scan_helpers import resolve_default_warehouse


LISTING_MAX_FILE_SIZE_MB = getattr(settings, "LISTING_MAX_FILE_SIZE_MB", 10)


def init_listing_state():
    return {
        "listing_stage": None,
        "listing_columns": [],
        "listing_rows": [],
        "listing_errors": [],
        "listing_sheet_names": [],
        "listing_sheet_name": "",
        "listing_header_row": 1,
        "listing_pdf_pages_mode": "all",
        "listing_pdf_page_start": "",
        "listing_pdf_page_end": "",
        "listing_pdf_total_pages": "",
        "listing_file_type": "",
    }


def clear_pending_listing(request):
    pending_data = request.session.pop("pallet_listing_pending", None)
    if pending_data and pending_data.get("file_path"):
        try:
            Path(pending_data["file_path"]).unlink(missing_ok=True)
        except OSError:
            pass


def hydrate_listing_state_from_pending(state, pending_data):
    if not pending_data:
        return None
    receipt_meta = pending_data.get("receipt_meta") or {}
    pdf_pages = pending_data.get("pdf_pages") or {}
    extension = pending_data.get("extension")
    sheet_names = pending_data.get("sheet_names") or []
    sheet_names_display = ", ".join(sheet_names) if sheet_names else ""
    sheet_name_value = pending_data.get("sheet_name") if extension in {".xlsx", ".xls"} else ""
    header_row_value = pending_data.get("header_row") if extension in {".xlsx", ".xls"} else ""
    pdf_pages_label = ""
    if extension == ".pdf":
        if pdf_pages.get("mode") == "custom" and pdf_pages.get("start") and pdf_pages.get("end"):
            pdf_pages_label = f"{pdf_pages['start']} - {pdf_pages['end']}"
        else:
            pdf_pages_label = "Toutes les pages"
    source_contact = Contact.objects.filter(
        id=receipt_meta.get("source_contact_id")
    ).first()
    carrier_contact = Contact.objects.filter(
        id=receipt_meta.get("carrier_contact_id")
    ).first()
    listing_meta = {
        "received_on": receipt_meta.get("received_on"),
        "pallet_count": receipt_meta.get("pallet_count"),
        "source_contact": source_contact.name if source_contact else "",
        "carrier_contact": carrier_contact.name if carrier_contact else "",
        "transport_request_date": receipt_meta.get("transport_request_date") or "",
        "sheet_name": sheet_name_value or "",
        "header_row": header_row_value or "",
        "sheet_names": sheet_names_display if extension in {".xlsx", ".xls"} else "",
        "pdf_pages": pdf_pages_label,
        "pdf_total_pages": pdf_pages.get("total") if extension == ".pdf" else "",
    }

    if extension in {".xlsx", ".xls"} and sheet_names and not state["listing_sheet_names"]:
        state["listing_sheet_names"] = sheet_names
    if sheet_name_value:
        state["listing_sheet_name"] = sheet_name_value
    if header_row_value:
        state["listing_header_row"] = header_row_value
    if pdf_pages.get("mode"):
        state["listing_pdf_pages_mode"] = pdf_pages.get("mode")
    if pdf_pages.get("start") is not None:
        state["listing_pdf_page_start"] = str(pdf_pages.get("start"))
    if pdf_pages.get("end") is not None:
        state["listing_pdf_page_end"] = str(pdf_pages.get("end"))
    if pdf_pages.get("total"):
        state["listing_pdf_total_pages"] = str(pdf_pages.get("total"))
    if pending_data.get("file_type"):
        state["listing_file_type"] = pending_data.get("file_type")

    return listing_meta


def handle_pallet_listing_action(
    request,
    *,
    action,
    listing_form,
    state,
):
    listing_errors = state["listing_errors"]

    if action == "listing_cancel":
        clear_pending_listing(request)
        return redirect("scan:scan_receive_pallet")

    if action == "listing_upload":
        listing_file_type = (request.POST.get("listing_file_type") or "").strip()
        listing_pdf_pages_mode = (
            request.POST.get("listing_pdf_pages_mode") or "all"
        ).strip()
        listing_pdf_page_start = (request.POST.get("listing_pdf_page_start") or "").strip()
        listing_pdf_page_end = (request.POST.get("listing_pdf_page_end") or "").strip()
        listing_sheet_name = (request.POST.get("listing_sheet_name") or "").strip()
        header_row_raw = (request.POST.get("listing_header_row") or "").strip()
        pdf_page_start = None
        pdf_page_end = None
        listing_header_row = state["listing_header_row"] or 1
        header_row_error = None

        if header_row_raw:
            try:
                listing_header_row = parse_int(header_row_raw)
            except ValueError:
                header_row_error = "Ligne des titres invalide."
        if not listing_form.is_valid():
            listing_errors.append("Renseignez les informations de réception.")
        uploaded = request.FILES.get("listing_file")
        if not uploaded:
            listing_errors.append("Fichier requis pour importer le listing.")
        else:
            max_size_bytes = LISTING_MAX_FILE_SIZE_MB * 1024 * 1024
            if uploaded.size and uploaded.size > max_size_bytes:
                listing_errors.append(
                    f"Fichier trop volumineux (> {LISTING_MAX_FILE_SIZE_MB} MB)."
                )
            extension = Path(uploaded.name).suffix.lower()
            if extension == ".pdf":
                listing_file_type = "pdf"
            elif extension in {".xlsx", ".xls"}:
                listing_file_type = "excel"
            elif extension == ".csv":
                listing_file_type = "csv"
            if extension not in {".csv", ".xlsx", ".xls", ".pdf"}:
                listing_errors.append("Format de fichier non supporté.")
            elif listing_errors:
                pass
            else:
                data = uploaded.read()
                sheet_names = []
                if extension in {".xlsx", ".xls"} and not listing_errors:
                    if header_row_error:
                        listing_errors.append(header_row_error)
                    if listing_header_row < 1:
                        listing_errors.append("Ligne des titres invalide (>= 1).")
                        listing_header_row = 1
                    try:
                        sheet_names = list_excel_sheets(data, extension)
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                    if sheet_names:
                        state["listing_sheet_names"] = sheet_names
                        if listing_sheet_name:
                            if listing_sheet_name not in sheet_names:
                                listing_errors.append(
                                    f"Feuille inconnue: {listing_sheet_name}."
                                )
                        else:
                            listing_sheet_name = sheet_names[0]
                if extension == ".pdf" and listing_pdf_pages_mode == "custom" and not listing_errors:
                    try:
                        state["listing_pdf_total_pages"] = str(get_pdf_page_count(data))
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                    if listing_pdf_page_start:
                        try:
                            pdf_page_start = parse_int(listing_pdf_page_start)
                        except ValueError:
                            listing_errors.append("Page PDF début invalide.")
                    if listing_pdf_page_end:
                        try:
                            pdf_page_end = parse_int(listing_pdf_page_end)
                        except ValueError:
                            listing_errors.append("Page PDF fin invalide.")
                    if not listing_errors:
                        pdf_page_start = pdf_page_start or 1
                        pdf_page_end = (
                            pdf_page_end
                            if pdf_page_end is not None
                            else int(state["listing_pdf_total_pages"])
                        )
                    if pdf_page_start is not None and pdf_page_end is not None:
                        if pdf_page_start < 1 or pdf_page_end < pdf_page_start:
                            listing_errors.append("Plage de pages PDF invalide.")
                    if listing_errors:
                        pdf_page_start = None
                        pdf_page_end = None
                if extension == ".pdf" and listing_pdf_pages_mode != "custom" and not listing_errors:
                    try:
                        state["listing_pdf_total_pages"] = str(get_pdf_page_count(data))
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                if not listing_errors:
                    extract_options = build_listing_extract_options(
                        extension,
                        listing_sheet_name,
                        listing_header_row,
                        listing_pdf_pages_mode,
                        pdf_page_start,
                        pdf_page_end,
                    )
                    try:
                        headers, rows = extract_tabular_data(
                            data,
                            extension,
                            **extract_options,
                        )
                        if not rows:
                            listing_errors.append("Fichier vide ou sans lignes exploitables.")
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                if not listing_errors:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=extension
                    ) as temp_file:
                        temp_file.write(data)
                        temp_path = temp_file.name
                    mapping_defaults = build_listing_mapping_defaults(headers)
                    pending = {
                        "token": uuid.uuid4().hex,
                        "file_path": temp_path,
                        "extension": extension,
                        "headers": headers,
                        "mapping": mapping_defaults,
                        "sheet_names": sheet_names,
                        "sheet_name": listing_sheet_name,
                        "header_row": listing_header_row,
                        "file_type": listing_file_type,
                        "pdf_pages": {
                            "mode": listing_pdf_pages_mode,
                            "start": pdf_page_start,
                            "end": pdf_page_end,
                            "total": int(state["listing_pdf_total_pages"] or 0) or "",
                        },
                        "receipt_meta": {
                            "received_on": listing_form.cleaned_data["received_on"].isoformat(),
                            "pallet_count": listing_form.cleaned_data["pallet_count"],
                            "source_contact_id": listing_form.cleaned_data["source_contact"].id,
                            "carrier_contact_id": listing_form.cleaned_data["carrier_contact"].id,
                            "transport_request_date": (
                                listing_form.cleaned_data["transport_request_date"].isoformat()
                                if listing_form.cleaned_data["transport_request_date"]
                                else ""
                            ),
                        },
                    }
                    request.session["pallet_listing_pending"] = pending
                    state["listing_stage"] = "mapping"
                    state["listing_columns"] = build_listing_columns(
                        headers, rows, mapping_defaults
                    )
        state["listing_file_type"] = listing_file_type
        state["listing_pdf_pages_mode"] = listing_pdf_pages_mode
        state["listing_pdf_page_start"] = listing_pdf_page_start
        state["listing_pdf_page_end"] = listing_pdf_page_end
        state["listing_sheet_name"] = listing_sheet_name
        state["listing_header_row"] = listing_header_row
        return None

    if action == "listing_map":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_pallet")
        headers = pending.get("headers") or []
        mapping = {}
        used_fields = {}
        for idx, _header in enumerate(headers):
            field = (request.POST.get(f"map_{idx}") or "").strip()
            if not field:
                continue
            if field in used_fields:
                listing_errors.append(
                    f"Champ {field} assigne deux fois ({used_fields[field]})."
                )
                continue
            mapping[idx] = field
            used_fields[field] = idx + 1
        missing_fields = PALLET_LISTING_REQUIRED_FIELDS - set(mapping.values())
        if missing_fields:
            listing_errors.append(
                "Champs requis manquants: " + ", ".join(sorted(missing_fields))
            )
        if listing_errors:
            state["listing_stage"] = "mapping"
            headers, rows = load_listing_table(pending)
            state["listing_columns"] = build_listing_columns(headers, rows, mapping)
        else:
            pending["mapping"] = mapping
            request.session["pallet_listing_pending"] = pending
            headers, rows = load_listing_table(pending)
            state["listing_rows"] = build_listing_review_rows(rows, mapping)
            state["listing_stage"] = "review"
        return None

    if action == "listing_confirm":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_pallet")
        headers, rows = load_listing_table(pending)
        mapping = pending.get("mapping") or {}
        mapped_rows = apply_listing_mapping(rows, mapping)
        receipt_meta = pending.get("receipt_meta") or {}

        warehouse = resolve_default_warehouse()
        if not warehouse:
            messages.error(request, "Aucun entrepôt configuré.")
            return redirect("scan:scan_receive_pallet")

        row_payloads = []
        for row_index, row in enumerate(mapped_rows, start=2):
            apply_flag = bool(request.POST.get(f"row_{row_index}_apply"))
            row_data = {}
            if apply_flag:
                for field, _ in PALLET_REVIEW_FIELDS:
                    row_data[field] = request.POST.get(
                        f"row_{row_index}_{field}"
                    ) or row.get(field)
                for key, _ in PALLET_LOCATION_FIELDS:
                    row_data[key] = request.POST.get(
                        f"row_{row_index}_{key}"
                    ) or row.get(key)
                row_data["quantity"] = request.POST.get(
                    f"row_{row_index}_quantity"
                ) or row.get("quantity")
                row_data["rack_color"] = request.POST.get(
                    f"row_{row_index}_rack_color"
                ) or row.get("rack_color")
            row_payloads.append(
                {
                    "apply": apply_flag,
                    "row_index": row_index,
                    "row_data": row_data,
                    "selection": request.POST.get(f"row_{row_index}_match") or "",
                    "override_code": request.POST.get(f"row_{row_index}_match_override") or "",
                }
            )

        with transaction.atomic():
            created, skipped, errors, receipt = apply_pallet_listing_import(
                row_payloads,
                user=request.user,
                warehouse=warehouse,
                receipt_meta=receipt_meta,
            )

        if errors:
            messages.error(request, f"Import terminé avec {len(errors)} erreur(s).")
            for error in errors[:10]:
                messages.error(request, error)
        if created and receipt:
            messages.success(
                request,
                f"{created} ligne(s) réceptionnée(s) (ref {receipt.reference}).",
            )
        elif not created:
            messages.error(request, "Aucune ligne valide à importer.")
        if skipped:
            messages.warning(request, f"{skipped} ligne(s) ignorée(s).")
        clear_pending_listing(request)
        return redirect("scan:scan_receive_pallet")

    return None
