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
SUPPORTED_PRODUCT_EXTENSIONS = {".csv", ".xlsx", ".xlsm", ".xls"}
PRODUCT_IMPORT_PENDING_KEY = "product_import_pending"
MAX_IMPORT_MESSAGES = 3
DEFAULT_PRODUCT_MATCH_ACTION = "update"
CREATE_ACTION = "create"
UPDATE_ACTION = "update"
PRODUCT_IMPORT_START_INDEX_FILE = 2
PRODUCT_IMPORT_START_INDEX_SINGLE = 1

ACTION_PRODUCT_CONFIRM = "product_confirm"
ACTION_PRODUCT_SINGLE = "product_single"
ACTION_PRODUCT_FILE = "product_file"

IMPORT_FILE_ACTIONS = {
    "location_file": ("emplacements", import_locations),
    "category_file": ("categories", import_categories),
    "warehouse_file": ("entrepôts", import_warehouses),
    "contact_file": ("contacts", import_contacts),
    "user_file": ("utilisateurs", import_users),
}

IMPORT_SINGLE_ACTIONS = {
    "location_single": ("emplacement", import_locations),
    "category_single": ("categorie", import_categories),
    "warehouse_single": ("entrepôt", import_warehouses),
    "contact_single": ("contact", import_contacts),
    "user_single": ("utilisateur", import_users),
}

PRODUCT_ACTION_HANDLERS = {
    ACTION_PRODUCT_SINGLE: lambda request, **_: _handle_product_single_action(request),
    ACTION_PRODUCT_FILE: lambda request, **_: _handle_product_file_action(request),
}


def render_scan_import(request, pending_import):
    context = dict(IMPORT_BASE_CONTEXT)
    context["product_match_pending"] = build_match_context(pending_import)
    return render(request, IMPORT_TEMPLATE, context)


def _redirect_scan_import():
    return redirect("scan:scan_import")


def _add_limited_message_list(request, *, title, entries, label):
    if not entries:
        return
    messages.warning(request, f"{title}: {len(entries)} {label}(s).")
    for message in entries[:MAX_IMPORT_MESSAGES]:
        messages.warning(request, message)


def _notify_import_result(request, *, title, created, updated, errors, warnings):
    _add_limited_message_list(request, title=title, entries=errors, label="erreur")
    _add_limited_message_list(request, title=title, entries=warnings, label="alerte")
    messages.success(request, f"{title}: {created} créé(s), {updated} maj.")


def _get_pending_import(request):
    return request.session.get(PRODUCT_IMPORT_PENDING_KEY)


def _set_pending_import(request, pending):
    request.session[PRODUCT_IMPORT_PENDING_KEY] = pending


def _importer_accepts_default_password(action):
    return action in {"user_file", "user_single"}


def _invoke_importer(importer, *, action, rows, default_password):
    if _importer_accepts_default_password(action):
        return importer(rows, default_password)
    return importer(rows)


def _build_pending_decisions(request, pending):
    default_action = pending.get("default_action", DEFAULT_PRODUCT_MATCH_ACTION)
    decisions = {}
    for item in pending.get("matches", []):
        row_index = item.get("row_index")
        action_choice = request.POST.get(f"decision_{row_index}") or default_action
        if action_choice == CREATE_ACTION:
            decisions[row_index] = {"action": CREATE_ACTION}
            continue
        match_id = request.POST.get(f"match_id_{row_index}")
        if not match_id:
            messages.error(
                request,
                "Import produit: sélection requise pour la mise à jour.",
            )
            return None
        match_ids = {str(match_id_value) for match_id_value in item.get("match_ids", [])}
        if str(match_id) not in match_ids:
            messages.error(
                request,
                "Import produit: produit cible invalide.",
            )
            return None
        decisions[row_index] = {
            "action": UPDATE_ACTION,
            "product_id": int(match_id),
        }
    return decisions


def _load_pending_rows(*, pending, clear_pending_import):
    if pending.get("source") != "file":
        return pending.get("rows", []), None, pending.get("start_index", PRODUCT_IMPORT_START_INDEX_SINGLE)

    temp_path = Path(pending.get("temp_path", ""))
    if not temp_path.exists():
        clear_pending_import()
        return None, None, None

    extension = pending.get("extension", "")
    data = temp_path.read_bytes()
    rows = list(iter_import_rows(data, extension))
    return rows, temp_path.parent, pending.get("start_index", PRODUCT_IMPORT_START_INDEX_FILE)


def _build_match_entry(*, row_index, match_type, matches, row):
    return {
        "row_index": row_index,
        "match_type": match_type,
        "match_ids": [product.id for product in matches],
        "row_summary": summarize_import_row(row),
    }


def _collect_file_matches(rows):
    matches = []
    for index, row in enumerate(rows, start=PRODUCT_IMPORT_START_INDEX_FILE):
        if row_is_empty(row):
            continue
        sku, name, brand = extract_product_identity(row)
        matched, match_type = find_product_matches(
            sku=sku, name=name, brand=brand
        )
        if matched:
            matches.append(
                _build_match_entry(
                    row_index=index,
                    match_type=match_type,
                    matches=matched,
                    row=row,
                )
            )
    return matches


def _build_product_pending(
    *,
    source,
    matches,
    default_action,
    start_index,
    rows=None,
    temp_path=None,
    extension="",
):
    pending = {
        "token": uuid.uuid4().hex,
        "source": source,
        "start_index": start_index,
        "default_action": default_action,
        "matches": matches,
    }
    if rows is not None:
        pending["rows"] = rows
    if temp_path:
        pending["temp_path"] = temp_path
    if extension:
        pending["extension"] = extension
    return pending


def _read_product_file_upload(uploaded):
    extension = Path(uploaded.name).suffix.lower()
    data = uploaded.read()
    if extension == ".csv":
        data = decode_text(data).encode("utf-8")
    return extension, data


def _unsupported_product_extension(extension):
    return extension not in SUPPORTED_PRODUCT_EXTENSIONS


def _handle_product_confirm_action(request, *, clear_pending_import):
    pending = _get_pending_import(request)
    token = (request.POST.get("pending_token") or "").strip()
    if not pending or token != pending.get("token"):
        messages.error(request, "Import produit: confirmation invalide.")
        return _redirect_scan_import()
    if request.POST.get("cancel"):
        clear_pending_import()
        messages.info(request, "Import produit annule.")
        return _redirect_scan_import()

    decisions = _build_pending_decisions(request, pending)
    if decisions is None:
        return _redirect_scan_import()

    rows, base_dir, start_index = _load_pending_rows(
        pending=pending,
        clear_pending_import=clear_pending_import,
    )
    if rows is None:
        messages.error(request, "Import produit: fichier temporaire introuvable.")
        return _redirect_scan_import()

    created, updated, errors, warnings = import_products_rows(
        rows,
        user=request.user,
        decisions=decisions,
        base_dir=base_dir,
        start_index=start_index,
    )
    clear_pending_import()
    _notify_import_result(
        request,
        title="Import produits",
        created=created,
        updated=updated,
        errors=errors,
        warnings=warnings,
    )
    return _redirect_scan_import()


def _handle_product_single_action(request):
    row = {
        key: value
        for key, value in request.POST.items()
        if key not in {"csrfmiddlewaretoken", "action"}
    }
    sku, name, brand = extract_product_identity(row)
    matches, match_type = find_product_matches(sku=sku, name=name, brand=brand)
    if matches:
        pending = _build_product_pending(
            source="single",
            rows=[row],
            start_index=PRODUCT_IMPORT_START_INDEX_SINGLE,
            default_action=DEFAULT_PRODUCT_MATCH_ACTION,
            matches=[
                _build_match_entry(
                    row_index=PRODUCT_IMPORT_START_INDEX_SINGLE,
                    match_type=match_type,
                    matches=matches,
                    row=row,
                )
            ],
        )
        _set_pending_import(request, pending)
        return render_scan_import(request, pending)

    created, updated, errors, warnings = import_products_rows(
        [row],
        user=request.user,
        start_index=PRODUCT_IMPORT_START_INDEX_SINGLE,
    )
    if errors:
        messages.error(request, errors[0])
    else:
        for message in warnings[:MAX_IMPORT_MESSAGES]:
            messages.warning(request, message)
        messages.success(request, "Produit créé.")
    return _redirect_scan_import()


def _handle_product_file_action(request):
    uploaded = request.FILES.get("import_file")
    update_existing = bool(request.POST.get("update_existing"))
    if not uploaded:
        messages.error(request, "Fichier requis pour importer les produits.")
        return _redirect_scan_import()

    extension, data = _read_product_file_upload(uploaded)
    if _unsupported_product_extension(extension):
        messages.error(request, "Format non supporte. Utilisez CSV/XLS/XLSX.")
        return _redirect_scan_import()

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
        temp.write(data)
        temp_path = temp.name

    rows = list(iter_import_rows(data, extension))
    matches = _collect_file_matches(rows)
    if matches:
        pending = _build_product_pending(
            source="file",
            temp_path=temp_path,
            extension=extension,
            start_index=PRODUCT_IMPORT_START_INDEX_FILE,
            default_action=UPDATE_ACTION if update_existing else CREATE_ACTION,
            matches=matches,
        )
        _set_pending_import(request, pending)
        return render_scan_import(request, pending)

    created, updated, errors, warnings = import_products_rows(
        rows,
        user=request.user,
        base_dir=Path(temp_path).parent,
        start_index=PRODUCT_IMPORT_START_INDEX_FILE,
    )
    Path(temp_path).unlink(missing_ok=True)
    _notify_import_result(
        request,
        title="Import produits",
        created=created,
        updated=updated,
        errors=errors,
        warnings=warnings,
    )
    return _redirect_scan_import()


def _handle_import_file_action(request, *, action, default_password):
    label, importer = IMPORT_FILE_ACTIONS[action]
    uploaded = request.FILES.get("import_file")
    if not uploaded:
        messages.error(request, f"Fichier requis pour importer les {label}.")
        return _redirect_scan_import()

    extension = Path(uploaded.name).suffix.lower()
    data = uploaded.read()
    try:
        rows = iter_import_rows(data, extension)
        result = _invoke_importer(
            importer,
            action=action,
            rows=rows,
            default_password=default_password,
        )
    except ValueError as exc:
        messages.error(request, f"Import {label}: {exc}")
        return _redirect_scan_import()

    created, updated, errors, warnings = normalize_import_result(result)
    _notify_import_result(
        request,
        title=f"Import {label}",
        created=created,
        updated=updated,
        errors=errors,
        warnings=warnings,
    )
    return _redirect_scan_import()


def _handle_import_single_action(request, *, action, default_password):
    label, importer = IMPORT_SINGLE_ACTIONS[action]
    row = dict(request.POST.items())
    try:
        result = _invoke_importer(
            importer,
            action=action,
            rows=[row],
            default_password=default_password,
        )
    except ValueError as exc:
        messages.error(request, f"Ajout {label}: {exc}")
        return _redirect_scan_import()

    created, updated, errors, warnings = normalize_import_result(result)
    if errors:
        messages.error(request, errors[0])
    elif warnings:
        for message in warnings[:MAX_IMPORT_MESSAGES]:
            messages.warning(request, message)
    else:
        messages.success(request, f"{label.capitalize()} ajouté.")
    return _redirect_scan_import()


def handle_scan_import_action(request, *, default_password, clear_pending_import):
    action = (request.POST.get("action") or "").strip()
    if not action:
        return None

    if action == ACTION_PRODUCT_CONFIRM:
        return _handle_product_confirm_action(
            request,
            clear_pending_import=clear_pending_import,
        )

    product_handler = PRODUCT_ACTION_HANDLERS.get(action)
    if product_handler:
        return product_handler(
            request,
            default_password=default_password,
            clear_pending_import=clear_pending_import,
        )

    if action in IMPORT_FILE_ACTIONS:
        return _handle_import_file_action(
            request,
            action=action,
            default_password=default_password,
        )

    if action in IMPORT_SINGLE_ACTIONS:
        return _handle_import_single_action(
            request,
            action=action,
            default_password=default_password,
        )

    return None
