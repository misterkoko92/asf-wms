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
    analyze_pdf_listing,
    extract_tabular_data,
    get_pdf_page_count,
    list_excel_sheets,
    parse_int,
)
from .models import Receipt, ReceiptType
from .pallet_listing import (
    PALLET_LISTING_REQUIRED_FIELDS,
    PALLET_LOCATION_FIELDS,
    PALLET_REVIEW_FIELDS,
    apply_listing_group_suggestion_to_overrides,
    apply_listing_mapping,
    build_listing_columns,
    build_listing_extract_options,
    build_listing_mapping_defaults,
    build_listing_review_state,
    capture_listing_review_overrides_from_post,
    load_listing_table,
)
from .scan_helpers import resolve_default_warehouse

LISTING_MAX_FILE_SIZE_MB = getattr(settings, "LISTING_MAX_FILE_SIZE_MB", 10)


def init_listing_state():
    return {
        "listing_stage": None,
        "listing_columns": [],
        "listing_rows": [],
        "listing_group_suggestions": [],
        "listing_errors": [],
        "listing_sheet_names": [],
        "listing_sheet_name": "",
        "listing_header_row": 1,
        "listing_pdf_pages_mode": "all",
        "listing_pdf_page_start": "",
        "listing_pdf_page_end": "",
        "listing_pdf_total_pages": "",
        "listing_pdf_analysis": None,
        "listing_file_type": "",
        "listing_entry_file_type": "",
        "listing_entry_receipt_id": "",
        "listing_selected_receipt": None,
    }


def clear_pending_listing(request):
    pending_data = request.session.pop("pallet_listing_pending", None)
    if pending_data and pending_data.get("file_path"):
        try:
            Path(pending_data["file_path"]).unlink(missing_ok=True)
        except OSError:
            pass


def _build_pending_pdf_pages_payload(*, mode, start, end, total, page_numbers=None):
    payload = {
        "mode": mode,
        "start": start,
        "end": end,
        "total": total,
    }
    if mode == "detected" and page_numbers:
        payload["pages"] = list(page_numbers)
    return payload


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
        if pdf_pages.get("mode") == "detected" and pdf_pages.get("pages"):
            pdf_pages_label = ", ".join(str(page) for page in pdf_pages.get("pages") or [])
        elif pdf_pages.get("mode") == "custom" and pdf_pages.get("start") and pdf_pages.get("end"):
            pdf_pages_label = f"{pdf_pages['start']} - {pdf_pages['end']}"
        else:
            pdf_pages_label = "Toutes les pages"
    selected_receipt = None
    receipt_id = pending_data.get("receipt_id")
    if receipt_id:
        selected_receipt = (
            Receipt.objects.select_related("source_contact", "carrier_contact")
            .filter(pk=receipt_id, receipt_type=ReceiptType.PALLET)
            .first()
        )
    source_contact = None
    carrier_contact = None
    if selected_receipt is not None:
        source_contact = selected_receipt.source_contact
        carrier_contact = selected_receipt.carrier_contact
    else:
        source_contact_id = receipt_meta.get("source_contact_id")
        carrier_contact_id = receipt_meta.get("carrier_contact_id")
        source_contact = (
            Contact.objects.filter(id=source_contact_id).first() if source_contact_id else None
        )
        carrier_contact = (
            Contact.objects.filter(id=carrier_contact_id).first() if carrier_contact_id else None
        )
    listing_meta = {
        "received_on": (
            selected_receipt.received_on.isoformat()
            if selected_receipt is not None and selected_receipt.received_on
            else receipt_meta.get("received_on") or ""
        ),
        "pallet_count": (
            selected_receipt.pallet_count
            if selected_receipt is not None
            else receipt_meta.get("pallet_count") or ""
        ),
        "source_contact": source_contact.name if source_contact else "",
        "carrier_contact": carrier_contact.name if carrier_contact else "",
        "transport_request_date": (
            selected_receipt.transport_request_date.isoformat()
            if selected_receipt is not None and selected_receipt.transport_request_date
            else receipt_meta.get("transport_request_date") or ""
        ),
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
    state["listing_entry_file_type"] = (
        pending_data.get("entry_file_type") or pending_data.get("file_type") or ""
    )
    state["listing_entry_receipt_id"] = str(receipt_id or "")
    state["listing_selected_receipt"] = selected_receipt
    if pending_data.get("pdf_analysis"):
        state["listing_pdf_analysis"] = pending_data.get("pdf_analysis")
        if not pending_data.get("headers"):
            state["listing_stage"] = "analysis"

    return listing_meta


def _parse_pdf_pages_selection(
    *,
    listing_errors,
    total_pages,
    pages_mode,
    page_start_raw,
    page_end_raw,
    default_pages=None,
    default_start=None,
    default_end=None,
):
    if pages_mode == "custom":
        resolved_mode = "custom"
    elif pages_mode == "detected":
        resolved_mode = "detected"
    else:
        resolved_mode = "all"
    if resolved_mode == "all":
        return resolved_mode, None, None, None
    if resolved_mode == "detected":
        detected_pages = []
        for value in default_pages or []:
            try:
                number = parse_int(value)
            except ValueError:
                continue
            if number is None or number < 1 or number > total_pages or number in detected_pages:
                continue
            detected_pages.append(number)
        if not detected_pages:
            listing_errors.append("Aucune page PDF détectée comme exploitable.")
            return resolved_mode, None, None, None
        return resolved_mode, detected_pages[0], detected_pages[-1], detected_pages

    page_start = None
    page_end = None
    if page_start_raw:
        try:
            page_start = parse_int(page_start_raw)
        except ValueError:
            listing_errors.append("Page PDF début invalide.")
    if page_end_raw:
        try:
            page_end = parse_int(page_end_raw)
        except ValueError:
            listing_errors.append("Page PDF fin invalide.")
    if listing_errors:
        return resolved_mode, None, None, None

    page_start = page_start or default_start or 1
    page_end = page_end if page_end is not None else (default_end or total_pages)
    if (
        page_start is None
        or page_end is None
        or page_start < 1
        or page_end < page_start
        or page_end > total_pages
    ):
        listing_errors.append("Plage de pages PDF invalide.")
        return resolved_mode, None, None, None
    return resolved_mode, page_start, page_end, None


def handle_pallet_listing_action(
    request,
    *,
    action,
    listing_form=None,
    state,
):
    listing_errors = state["listing_errors"]

    if action == "listing_cancel":
        clear_pending_listing(request)
        request.session.pop("pallet_listing_last_incomplete_product_ids", None)
        return redirect("scan:scan_receive_listing")

    if action == "listing_upload":
        pending_config = request.session.get("pallet_listing_pending") or {}
        selected_receipt_id = pending_config.get("receipt_id")
        selected_receipt = None
        listing_file_type = (request.POST.get("listing_file_type") or "").strip()
        listing_pdf_pages_mode = (request.POST.get("listing_pdf_pages_mode") or "all").strip()
        listing_pdf_page_start = (request.POST.get("listing_pdf_page_start") or "").strip()
        listing_pdf_page_end = (request.POST.get("listing_pdf_page_end") or "").strip()
        listing_sheet_name = (request.POST.get("listing_sheet_name") or "").strip()
        header_row_raw = (request.POST.get("listing_header_row") or "").strip()
        pdf_page_start = None
        pdf_page_end = None
        pdf_page_numbers = None
        listing_header_row = state["listing_header_row"] or 1
        header_row_error = None

        if not selected_receipt_id:
            listing_errors.append("Sélectionnez une réception liée avant d'importer le listing.")
        else:
            selected_receipt = (
                Receipt.objects.select_related("source_contact", "carrier_contact")
                .filter(pk=selected_receipt_id, receipt_type=ReceiptType.PALLET)
                .first()
            )
            if selected_receipt is None:
                listing_errors.append("Réception liée introuvable.")
        if header_row_raw:
            try:
                listing_header_row = parse_int(header_row_raw)
            except ValueError:
                header_row_error = "Ligne des titres invalide."
        uploaded = request.FILES.get("listing_file")
        if not uploaded:
            listing_errors.append("Fichier requis pour importer le listing.")
        else:
            max_size_bytes = LISTING_MAX_FILE_SIZE_MB * 1024 * 1024
            if uploaded.size and uploaded.size > max_size_bytes:
                listing_errors.append(f"Fichier trop volumineux (> {LISTING_MAX_FILE_SIZE_MB} MB).")
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
                                listing_errors.append(f"Feuille inconnue: {listing_sheet_name}.")
                        else:
                            listing_sheet_name = sheet_names[0]
                if extension == ".pdf" and not listing_errors:
                    try:
                        analysis = analyze_pdf_listing(data)
                    except ValueError as exc:
                        listing_errors.append(str(exc))
                    else:
                        state["listing_pdf_analysis"] = analysis
                        state["listing_pdf_total_pages"] = str(analysis["total_pages"])
                        recommended_pages = analysis.get("recommended_pages") or {}
                        listing_pdf_pages_mode = (
                            recommended_pages.get("mode")
                            if recommended_pages.get("mode") in {"all", "custom", "detected"}
                            else "all"
                        )
                        pdf_page_start = recommended_pages.get("start")
                        pdf_page_end = recommended_pages.get("end")
                        pdf_page_numbers = recommended_pages.get("pages") or []
                if extension != ".pdf" and not listing_errors:
                    extract_options = build_listing_extract_options(
                        extension,
                        listing_sheet_name,
                        listing_header_row,
                        listing_pdf_pages_mode,
                        pdf_page_start,
                        pdf_page_end,
                        pdf_page_numbers,
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
                if extension == ".pdf" and not listing_errors:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                        temp_file.write(data)
                        temp_path = temp_file.name
                    pending = {
                        "entry_file_type": pending_config.get("entry_file_type")
                        or listing_file_type,
                        "receipt_id": selected_receipt_id,
                        "token": uuid.uuid4().hex,
                        "file_path": temp_path,
                        "extension": extension,
                        "sheet_names": sheet_names,
                        "sheet_name": listing_sheet_name,
                        "header_row": listing_header_row,
                        "file_type": listing_file_type,
                        "pdf_analysis": analysis,
                        "pdf_pages": {
                            **_build_pending_pdf_pages_payload(
                                mode=listing_pdf_pages_mode,
                                start=pdf_page_start,
                                end=pdf_page_end,
                                total=int(state["listing_pdf_total_pages"] or 0) or "",
                                page_numbers=pdf_page_numbers,
                            )
                        },
                        "receipt_meta": {
                            "received_on": (
                                selected_receipt.received_on.isoformat()
                                if selected_receipt and selected_receipt.received_on
                                else ""
                            ),
                            "pallet_count": (
                                selected_receipt.pallet_count if selected_receipt else ""
                            ),
                            "source_contact_id": (
                                selected_receipt.source_contact_id if selected_receipt else ""
                            ),
                            "carrier_contact_id": (
                                selected_receipt.carrier_contact_id if selected_receipt else ""
                            ),
                            "transport_request_date": (
                                selected_receipt.transport_request_date.isoformat()
                                if selected_receipt and selected_receipt.transport_request_date
                                else ""
                            ),
                        },
                    }
                    request.session["pallet_listing_pending"] = pending
                    request.session.pop("pallet_listing_last_incomplete_product_ids", None)
                    state["listing_stage"] = "analysis"
                elif not listing_errors:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
                        temp_file.write(data)
                        temp_path = temp_file.name
                    mapping_defaults = build_listing_mapping_defaults(headers)
                    pending = {
                        "entry_file_type": pending_config.get("entry_file_type")
                        or listing_file_type,
                        "receipt_id": selected_receipt_id,
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
                            **_build_pending_pdf_pages_payload(
                                mode=listing_pdf_pages_mode,
                                start=pdf_page_start,
                                end=pdf_page_end,
                                total=int(state["listing_pdf_total_pages"] or 0) or "",
                                page_numbers=pdf_page_numbers,
                            )
                        },
                        "receipt_meta": {
                            "received_on": (
                                selected_receipt.received_on.isoformat()
                                if selected_receipt and selected_receipt.received_on
                                else ""
                            ),
                            "pallet_count": (
                                selected_receipt.pallet_count if selected_receipt else ""
                            ),
                            "source_contact_id": (
                                selected_receipt.source_contact_id if selected_receipt else ""
                            ),
                            "carrier_contact_id": (
                                selected_receipt.carrier_contact_id if selected_receipt else ""
                            ),
                            "transport_request_date": (
                                selected_receipt.transport_request_date.isoformat()
                                if selected_receipt and selected_receipt.transport_request_date
                                else ""
                            ),
                        },
                    }
                    request.session["pallet_listing_pending"] = pending
                    request.session.pop("pallet_listing_last_incomplete_product_ids", None)
                    state["listing_stage"] = "mapping"
                    state["listing_columns"] = build_listing_columns(
                        headers, rows, mapping_defaults
                    )
        state["listing_file_type"] = listing_file_type
        state["listing_pdf_pages_mode"] = listing_pdf_pages_mode
        state["listing_pdf_page_start"] = str(pdf_page_start or listing_pdf_page_start or "")
        state["listing_pdf_page_end"] = str(pdf_page_end or listing_pdf_page_end or "")
        state["listing_sheet_name"] = listing_sheet_name
        state["listing_header_row"] = listing_header_row
        return None

    if action == "listing_pdf_extract":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_listing")
        if pending.get("extension") != ".pdf":
            messages.error(request, "Import PDF introuvable.")
            return redirect("scan:scan_receive_listing")

        analysis = pending.get("pdf_analysis") or {}
        total_pages = int(
            (pending.get("pdf_pages") or {}).get("total") or analysis.get("total_pages") or 0
        )
        listing_pdf_pages_mode = (request.POST.get("listing_pdf_pages_mode") or "all").strip()
        listing_pdf_page_start = (request.POST.get("listing_pdf_page_start") or "").strip()
        listing_pdf_page_end = (request.POST.get("listing_pdf_page_end") or "").strip()
        default_pages = analysis.get("recommended_pages") or {}
        (
            listing_pdf_pages_mode,
            pdf_page_start,
            pdf_page_end,
            pdf_page_numbers,
        ) = _parse_pdf_pages_selection(
            listing_errors=listing_errors,
            total_pages=total_pages,
            pages_mode=listing_pdf_pages_mode,
            page_start_raw=listing_pdf_page_start,
            page_end_raw=listing_pdf_page_end,
            default_pages=default_pages.get("pages") or analysis.get("extractable_pages") or [],
            default_start=default_pages.get("start"),
            default_end=default_pages.get("end"),
        )
        state["listing_stage"] = "analysis"
        state["listing_pdf_analysis"] = analysis
        state["listing_pdf_total_pages"] = str(total_pages or "")
        state["listing_file_type"] = "pdf"
        state["listing_pdf_pages_mode"] = listing_pdf_pages_mode
        state["listing_pdf_page_start"] = str(pdf_page_start or listing_pdf_page_start or "")
        state["listing_pdf_page_end"] = str(pdf_page_end or listing_pdf_page_end or "")
        if listing_errors:
            return None

        pending["pdf_pages"] = {
            **_build_pending_pdf_pages_payload(
                mode=listing_pdf_pages_mode,
                start=pdf_page_start,
                end=pdf_page_end,
                total=total_pages,
                page_numbers=pdf_page_numbers,
            ),
        }
        data = Path(pending["file_path"]).read_bytes()
        extract_options = build_listing_extract_options(
            ".pdf",
            "",
            1,
            listing_pdf_pages_mode,
            pdf_page_start,
            pdf_page_end,
            pdf_page_numbers,
        )
        try:
            headers, rows = extract_tabular_data(
                data,
                ".pdf",
                **extract_options,
            )
            if not rows:
                listing_errors.append("Fichier vide ou sans lignes exploitables.")
        except ValueError as exc:
            listing_errors.append(str(exc))
            return None
        if listing_errors:
            return None

        mapping_defaults = build_listing_mapping_defaults(headers)
        pending["headers"] = headers
        pending["mapping"] = mapping_defaults
        request.session["pallet_listing_pending"] = pending
        state["listing_stage"] = "mapping"
        state["listing_columns"] = build_listing_columns(headers, rows, mapping_defaults)
        return None

    if action == "listing_map":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_listing")
        headers = pending.get("headers") or []
        mapping = {}
        used_fields = {}
        for idx, _header in enumerate(headers):
            field = (request.POST.get(f"map_{idx}") or "").strip()
            if not field:
                continue
            if field in used_fields:
                listing_errors.append(f"Champ {field} assigne deux fois ({used_fields[field]}).")
                continue
            mapping[idx] = field
            used_fields[field] = idx + 1
        missing_fields = PALLET_LISTING_REQUIRED_FIELDS - set(mapping.values())
        if missing_fields:
            listing_errors.append("Champs requis manquants: " + ", ".join(sorted(missing_fields)))
        if listing_errors:
            state["listing_stage"] = "mapping"
            headers, rows = load_listing_table(pending)
            state["listing_columns"] = build_listing_columns(headers, rows, mapping)
        else:
            pending["mapping"] = mapping
            request.session["pallet_listing_pending"] = pending
            headers, rows = load_listing_table(pending)
            review_state = build_listing_review_state(rows, mapping)
            state["listing_rows"] = review_state["rows"]
            state["listing_group_suggestions"] = review_state["group_suggestions"]
            state["listing_stage"] = "review"
        return None

    if action.startswith("listing_apply_suggestion_group"):
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_listing")

        suggestion_id = action.partition(":")[2].strip()
        headers, rows = load_listing_table(pending)
        mapping = pending.get("mapping") or {}
        review_overrides = capture_listing_review_overrides_from_post(request.POST, rows, mapping)
        review_state = build_listing_review_state(rows, mapping, review_overrides=review_overrides)
        suggestion = next(
            (
                suggestion_item
                for suggestion_item in review_state["group_suggestions"]
                if suggestion_item.get("id") == suggestion_id
            ),
            None,
        )
        state["listing_stage"] = "review"
        if suggestion is None:
            listing_errors.append("Suggestion introuvable ou obsolète.")
            state["listing_rows"] = review_state["rows"]
            state["listing_group_suggestions"] = review_state["group_suggestions"]
            return None

        apply_listing_group_suggestion_to_overrides(review_overrides, suggestion)
        pending["review_overrides"] = review_overrides
        request.session["pallet_listing_pending"] = pending
        updated_review_state = build_listing_review_state(
            rows,
            mapping,
            review_overrides=review_overrides,
        )
        state["listing_rows"] = updated_review_state["rows"]
        state["listing_group_suggestions"] = updated_review_state["group_suggestions"]
        return None

    if action == "listing_confirm":
        pending = request.session.get("pallet_listing_pending")
        token = request.POST.get("pending_token")
        if not pending or pending.get("token") != token:
            messages.error(request, "Session d'import expirée.")
            return redirect("scan:scan_receive_listing")
        headers, rows = load_listing_table(pending)
        mapping = pending.get("mapping") or {}
        mapped_rows = apply_listing_mapping(rows, mapping)
        selected_receipt = None
        selected_receipt_id = pending.get("receipt_id")
        if selected_receipt_id:
            selected_receipt = (
                Receipt.objects.select_related("source_contact", "carrier_contact")
                .filter(pk=selected_receipt_id, receipt_type=ReceiptType.PALLET)
                .first()
            )
            if selected_receipt is None:
                messages.error(request, "Réception liée introuvable.")
                return redirect("scan:scan_receive_listing")
        else:
            messages.error(request, "Réception liée introuvable.")
            return redirect("scan:scan_receive_listing")

        warehouse = resolve_default_warehouse()
        if not warehouse:
            messages.error(request, "Aucun entrepôt configuré.")
            return redirect("scan:scan_receive_listing")

        row_payloads = []
        for row_index, row in enumerate(mapped_rows, start=2):
            apply_flag = bool(request.POST.get(f"row_{row_index}_apply"))
            row_data = {}
            if apply_flag:
                for field, _ in PALLET_REVIEW_FIELDS:
                    row_data[field] = request.POST.get(f"row_{row_index}_{field}") or row.get(field)
                for key, _ in PALLET_LOCATION_FIELDS:
                    row_data[key] = request.POST.get(f"row_{row_index}_{key}") or row.get(key)
                row_data["quantity"] = request.POST.get(f"row_{row_index}_quantity") or row.get(
                    "quantity"
                )
                row_data["rack_color"] = request.POST.get(f"row_{row_index}_rack_color") or row.get(
                    "rack_color"
                )
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
            created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
                row_payloads,
                user=request.user,
                warehouse=warehouse,
                receipt_meta={},
                existing_receipt=selected_receipt,
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
        if incomplete_product_ids:
            request.session["pallet_listing_last_incomplete_product_ids"] = incomplete_product_ids
        else:
            request.session.pop("pallet_listing_last_incomplete_product_ids", None)
        clear_pending_listing(request)
        return redirect("scan:scan_receive_listing")

    return None
