import tempfile
import uuid
from pathlib import Path

from django.contrib import messages
from django.shortcuts import redirect, render

from .import_results import normalize_import_result
from .import_services import (
    extract_product_identity,
    find_product_matches,
    import_categories,
    import_contacts,
    import_locations,
    import_products_rows,
    import_users,
    import_warehouses,
)
from .import_utils import decode_text, iter_import_rows
from .product_import_review import build_match_context, row_is_empty, summarize_import_row

IMPORT_TEMPLATE = "scan/imports.html"
IMPORT_BASE_CONTEXT = {"active": "imports", "shell_class": "scan-shell-wide"}

IMPORT_FILE_ACTIONS = {
    "location_file": ("emplacements", import_locations),
    "category_file": ("categories", import_categories),
    "warehouse_file": ("entrepots", import_warehouses),
    "contact_file": ("contacts", import_contacts),
    "user_file": ("utilisateurs", import_users),
}

IMPORT_SINGLE_ACTIONS = {
    "location_single": ("emplacement", import_locations),
    "category_single": ("categorie", import_categories),
    "warehouse_single": ("entrepot", import_warehouses),
    "contact_single": ("contact", import_contacts),
    "user_single": ("utilisateur", import_users),
}


def render_scan_import(request, pending_import):
    context = dict(IMPORT_BASE_CONTEXT)
    context["product_match_pending"] = build_match_context(pending_import)
    return render(request, IMPORT_TEMPLATE, context)


def handle_scan_import_action(request, *, default_password, clear_pending_import):
    action = (request.POST.get("action") or "").strip()
    if not action:
        return None

    if action == "product_confirm":
        pending = request.session.get("product_import_pending")
        token = (request.POST.get("pending_token") or "").strip()
        if not pending or token != pending.get("token"):
            messages.error(request, "Import produit: confirmation invalide.")
            return redirect("scan:scan_import")
        if request.POST.get("cancel"):
            clear_pending_import()
            messages.info(request, "Import produit annule.")
            return redirect("scan:scan_import")

        decisions = {}
        for item in pending.get("matches", []):
            row_index = item.get("row_index")
            action_choice = request.POST.get(f"decision_{row_index}") or pending.get(
                "default_action", "update"
            )
            if action_choice == "create":
                decisions[row_index] = {"action": "create"}
                continue
            match_id = request.POST.get(f"match_id_{row_index}")
            if not match_id:
                messages.error(
                    request,
                    "Import produit: selection requise pour la mise a jour.",
                )
                return redirect("scan:scan_import")
            if str(match_id) not in {str(mid) for mid in item.get("match_ids", [])}:
                messages.error(
                    request,
                    "Import produit: produit cible invalide.",
                )
                return redirect("scan:scan_import")
            decisions[row_index] = {
                "action": "update",
                "product_id": int(match_id),
            }

        if pending.get("source") == "file":
            temp_path = Path(pending["temp_path"])
            if not temp_path.exists():
                clear_pending_import()
                messages.error(request, "Import produit: fichier temporaire introuvable.")
                return redirect("scan:scan_import")
            extension = pending.get("extension", "")
            data = temp_path.read_bytes()
            rows = list(iter_import_rows(data, extension))
            base_dir = temp_path.parent
            start_index = pending.get("start_index", 2)
        else:
            rows = pending.get("rows", [])
            base_dir = None
            start_index = pending.get("start_index", 1)

        created, updated, errors, warnings = import_products_rows(
            rows,
            user=request.user,
            decisions=decisions,
            base_dir=base_dir,
            start_index=start_index,
        )
        clear_pending_import()
        if errors:
            messages.warning(request, f"Import produits: {len(errors)} erreur(s).")
            for message in errors[:3]:
                messages.warning(request, message)
        if warnings:
            messages.warning(request, f"Import produits: {len(warnings)} alerte(s).")
            for message in warnings[:3]:
                messages.warning(request, message)
        messages.success(
            request,
            f"Import produits: {created} cree(s), {updated} maj.",
        )
        return redirect("scan:scan_import")

    if action == "product_single":
        row = {
            key: value
            for key, value in request.POST.items()
            if key not in {"csrfmiddlewaretoken", "action"}
        }
        sku, name, brand = extract_product_identity(row)
        matches, match_type = find_product_matches(sku=sku, name=name, brand=brand)
        if matches:
            pending = {
                "token": uuid.uuid4().hex,
                "source": "single",
                "rows": [row],
                "start_index": 1,
                "default_action": "update",
                "matches": [
                    {
                        "row_index": 1,
                        "match_type": match_type,
                        "match_ids": [product.id for product in matches],
                        "row_summary": summarize_import_row(row),
                    }
                ],
            }
            request.session["product_import_pending"] = pending
            return render_scan_import(request, pending)
        created, updated, errors, warnings = import_products_rows(
            [row],
            user=request.user,
            start_index=1,
        )
        if errors:
            messages.error(request, errors[0])
        else:
            if warnings:
                for message in warnings[:3]:
                    messages.warning(request, message)
            messages.success(request, "Produit cree.")
        return redirect("scan:scan_import")

    if action == "product_file":
        uploaded = request.FILES.get("import_file")
        update_existing = bool(request.POST.get("update_existing"))
        if not uploaded:
            messages.error(request, "Fichier requis pour importer les produits.")
            return redirect("scan:scan_import")
        extension = Path(uploaded.name).suffix.lower()
        data = uploaded.read()
        if extension == ".csv":
            data = decode_text(data).encode("utf-8")
        if extension not in {".csv", ".xlsx", ".xlsm", ".xls"}:
            messages.error(request, "Format non supporte. Utilisez CSV/XLS/XLSX.")
            return redirect("scan:scan_import")
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
            temp.write(data)
            temp_path = temp.name
        rows = list(iter_import_rows(data, extension))
        matches = []
        for index, row in enumerate(rows, start=2):
            if row_is_empty(row):
                continue
            sku, name, brand = extract_product_identity(row)
            matched, match_type = find_product_matches(
                sku=sku, name=name, brand=brand
            )
            if matched:
                matches.append(
                    {
                        "row_index": index,
                        "match_type": match_type,
                        "match_ids": [product.id for product in matched],
                        "row_summary": summarize_import_row(row),
                    }
                )
        if matches:
            pending = {
                "token": uuid.uuid4().hex,
                "source": "file",
                "temp_path": temp_path,
                "extension": extension,
                "start_index": 2,
                "default_action": "update" if update_existing else "create",
                "matches": matches,
            }
            request.session["product_import_pending"] = pending
            return render_scan_import(request, pending)

        created, updated, errors, warnings = import_products_rows(
            rows,
            user=request.user,
            base_dir=Path(temp_path).parent,
            start_index=2,
        )
        Path(temp_path).unlink(missing_ok=True)
        if errors:
            messages.warning(request, f"Import produits: {len(errors)} erreur(s).")
            for message in errors[:3]:
                messages.warning(request, message)
        if warnings:
            messages.warning(request, f"Import produits: {len(warnings)} alerte(s).")
            for message in warnings[:3]:
                messages.warning(request, message)
        messages.success(
            request,
            f"Import produits: {created} cree(s), {updated} maj.",
        )
        return redirect("scan:scan_import")

    if action in IMPORT_FILE_ACTIONS:
        label, importer = IMPORT_FILE_ACTIONS[action]
        uploaded = request.FILES.get("import_file")
        if not uploaded:
            messages.error(request, f"Fichier requis pour importer les {label}.")
            return redirect("scan:scan_import")
        extension = Path(uploaded.name).suffix.lower()
        data = uploaded.read()
        try:
            rows = iter_import_rows(data, extension)
            if action == "user_file":
                result = importer(rows, default_password)
            else:
                result = importer(rows)
        except ValueError as exc:
            messages.error(request, f"Import {label}: {exc}")
            return redirect("scan:scan_import")
        created, updated, errors, warnings = normalize_import_result(result)
        if errors:
            messages.warning(request, f"Import {label}: {len(errors)} erreur(s).")
            for message in errors[:3]:
                messages.warning(request, message)
        if warnings:
            messages.warning(request, f"Import {label}: {len(warnings)} alerte(s).")
            for message in warnings[:3]:
                messages.warning(request, message)
        messages.success(
            request,
            f"Import {label}: {created} cree(s), {updated} maj.",
        )
        return redirect("scan:scan_import")

    if action in IMPORT_SINGLE_ACTIONS:
        label, importer = IMPORT_SINGLE_ACTIONS[action]
        row = dict(request.POST.items())
        try:
            if action == "user_single":
                result = importer([row], default_password)
            else:
                result = importer([row])
        except ValueError as exc:
            messages.error(request, f"Ajout {label}: {exc}")
            return redirect("scan:scan_import")
        created, updated, errors, warnings = normalize_import_result(result)
        if errors:
            messages.error(request, errors[0])
        elif warnings:
            for message in warnings[:3]:
                messages.warning(request, message)
        else:
            messages.success(request, f"{label.capitalize()} ajoute.")
        return redirect("scan:scan_import")

    return None
