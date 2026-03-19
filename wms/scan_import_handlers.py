import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from contacts.models import Contact, ContactType

from .exports import _build_contact_role_scope_maps
from .import_results import normalize_import_result
from .import_services import (
    DEFAULT_QUANTITY_MODE,
    extract_product_identity,
    find_product_matches,
    import_categories,
    import_contacts,
    import_locations,
    import_products_rows,
    import_users,
    import_warehouses,
    normalize_quantity_mode,
)
from .import_utils import decode_text, iter_import_rows
from .models import (
    Location,
    Product,
    ProductCategory,
    ProductTag,
    RackColor,
    Warehouse,
)
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
PRODUCT_STOCK_MODE_FIELD = "stock_mode"

ACTION_PRODUCT_CONFIRM = "product_confirm"
ACTION_PRODUCT_SINGLE = "product_single"
ACTION_PRODUCT_FILE = "product_file"

IMPORT_FILE_ACTIONS = {
    "location_file": (_lazy("emplacements"), import_locations),
    "category_file": (_lazy("categories"), import_categories),
    "warehouse_file": (_lazy("entrepôts"), import_warehouses),
    "contact_file": (_lazy("contacts"), import_contacts),
    "user_file": (_lazy("utilisateurs"), import_users),
}

IMPORT_SINGLE_ACTIONS = {
    "location_single": (_lazy("emplacement"), import_locations),
    "category_single": (_lazy("categorie"), import_categories),
    "warehouse_single": (_lazy("entrepôt"), import_warehouses),
    "contact_single": (_lazy("contact"), import_contacts),
    "user_single": (_lazy("utilisateur"), import_users),
}

PRODUCT_ACTION_HANDLERS = {
    ACTION_PRODUCT_SINGLE: lambda request, **_: _handle_product_single_action(request),
    ACTION_PRODUCT_FILE: lambda request, **_: _handle_product_file_action(request),
}


def _translate_runtime_message(message):
    if not message:
        return ""
    return str(_(str(message)))


def render_scan_import(request, pending_import):
    context = dict(IMPORT_BASE_CONTEXT)
    context["product_match_pending"] = build_match_context(pending_import)
    context["import_selector_data"] = _build_import_selector_data()
    context["import_default_password_configured"] = bool(
        getattr(settings, "IMPORT_DEFAULT_PASSWORD", None)
    )
    return render(request, IMPORT_TEMPLATE, context)


def _redirect_scan_import():
    return redirect("scan:scan_import")


def _stringify_decimal(value):
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _category_parts(category):
    parts = []
    current = category
    while current is not None:
        parts.append(current.name or "")
        current = current.parent
    parts.reverse()
    return parts


def _category_levels(category):
    parts = _category_parts(category)
    levels = parts[:4]
    while len(levels) < 4:
        levels.append("")
    return levels


def _pick_default_address(addresses):
    for address in addresses:
        if address.is_default:
            return address
    return addresses[0] if addresses else None


def _effective_contact_address(contact):
    if (
        contact.contact_type == ContactType.PERSON
        and contact.use_organization_address
        and contact.organization is not None
    ):
        return _pick_default_address(list(contact.organization.addresses.all()))
    return _pick_default_address(list(contact.addresses.all()))


def _build_rack_color_lookup():
    return {
        (rack_color.warehouse_id, rack_color.zone): rack_color.color
        for rack_color in RackColor.objects.only("warehouse_id", "zone", "color")
    }


def _build_warehouse_selector_data():
    return [
        {"name": warehouse.name, "code": warehouse.code}
        for warehouse in Warehouse.objects.only("name", "code").order_by("name")
    ]


def _build_location_selector_data():
    rack_color_lookup = _build_rack_color_lookup()
    return [
        {
            "warehouse": location.warehouse.name,
            "zone": location.zone,
            "aisle": location.aisle,
            "shelf": location.shelf,
            "rack_color": rack_color_lookup.get((location.warehouse_id, location.zone), ""),
            "notes": location.notes or "",
            "label": str(location),
        }
        for location in Location.objects.select_related("warehouse")
        .only("warehouse__name", "zone", "aisle", "shelf", "notes")
        .order_by("warehouse__name", "zone", "aisle", "shelf")
    ]


def _build_category_selector_data():
    categories = (
        ProductCategory.objects.select_related("parent__parent__parent")
        .only(
            "name",
            "parent__name",
            "parent__parent__name",
            "parent__parent__parent__name",
        )
        .order_by("name")
    )
    data = []
    for category in categories:
        level_1, level_2, level_3, level_4 = _category_levels(category)
        data.append(
            {
                "name": category.name,
                "parent": category.parent.name if category.parent else "",
                "path": " > ".join(part for part in _category_parts(category) if part),
                "level_1": level_1,
                "level_2": level_2,
                "level_3": level_3,
                "level_4": level_4,
            }
        )
    return sorted(data, key=lambda item: (item["path"], item["name"]))


def _build_product_selector_data():
    rack_color_lookup = _build_rack_color_lookup()
    products = (
        Product.objects.select_related(
            "category__parent__parent__parent",
            "default_location__warehouse",
        )
        .prefetch_related("tags")
        .only(
            "sku",
            "name",
            "brand",
            "barcode",
            "ean",
            "color",
            "pu_ht",
            "tva",
            "default_location__warehouse__name",
            "default_location__zone",
            "default_location__aisle",
            "default_location__shelf",
            "notes",
            "category__name",
            "category__parent__name",
            "category__parent__parent__name",
            "category__parent__parent__parent__name",
        )
        .order_by("name", "sku")
    )
    data = []
    for product in products:
        level_1, level_2, level_3, level_4 = _category_levels(product.category)
        location = product.default_location
        data.append(
            {
                "name": product.name,
                "sku": product.sku or "",
                "barcode": product.barcode or "",
                "ean": product.ean or "",
                "pu_ht": _stringify_decimal(product.pu_ht),
                "tva": _stringify_decimal(product.tva),
                "brand": product.brand or "",
                "color": product.color or "",
                "tags": "|".join(sorted(tag.name for tag in product.tags.all())),
                "category_l1": level_1,
                "category_l2": level_2,
                "category_l3": level_3,
                "category_l4": level_4,
                "warehouse": location.warehouse.name if location else "",
                "zone": location.zone if location else "",
                "aisle": location.aisle if location else "",
                "shelf": location.shelf if location else "",
                "rack_color": (
                    rack_color_lookup.get((location.warehouse_id, location.zone), "")
                    if location
                    else ""
                ),
                "notes": product.notes or "",
                "label": f"{product.sku} - {product.name}" if product.sku else product.name,
            }
        )
    return data


def _build_contact_selector_data():
    contacts = list(
        Contact.objects.select_related("organization")
        .prefetch_related("addresses", "organization__addresses")
        .order_by("name")
    )
    destination_ids_by_contact_id, scope_maps = _build_contact_role_scope_maps(
        [contact.id for contact in contacts if getattr(contact, "id", None)]
    )
    global_scope_contact_ids, destination_labels_by_id = scope_maps
    data = []
    for contact in contacts:
        address = _effective_contact_address(contact)
        scope_label = ""
        contact_id = getattr(contact, "id", None)
        if contact_id in global_scope_contact_ids:
            scope_label = "GLOBAL"
        else:
            destination_labels = [
                destination_labels_by_id[destination_id]
                for destination_id in sorted(
                    destination_ids_by_contact_id.get(contact_id, set()),
                    key=lambda destination_id: destination_labels_by_id.get(destination_id, ""),
                )
                if destination_id in destination_labels_by_id
            ]
            scope_label = " | ".join(destination_labels)
        data.append(
            {
                "name": contact.name,
                "contact_type": contact.contact_type,
                "email": contact.email or "",
                "phone": contact.phone or "",
                "scope": scope_label,
                "address_line1": address.address_line1 if address else "",
                "city": address.city if address else "",
                "label": contact.name,
            }
        )
    return data


def _build_user_selector_data():
    User = get_user_model()
    return [
        {
            "username": user.username,
            "email": user.email or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_staff": bool(user.is_staff),
            "is_superuser": bool(user.is_superuser),
            "is_active": bool(user.is_active),
            "label": user.username,
        }
        for user in User.objects.only(
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "is_active",
        ).order_by("username")
    ]


def _build_import_selector_data():
    return {
        "products": _build_product_selector_data(),
        "locations": _build_location_selector_data(),
        "warehouses": _build_warehouse_selector_data(),
        "categories": _build_category_selector_data(),
        "contacts": _build_contact_selector_data(),
        "users": _build_user_selector_data(),
        "product_tags": list(ProductTag.objects.order_by("name").values_list("name", flat=True)),
    }


def _add_limited_message_list(request, *, title, entries, label):
    if not entries:
        return
    messages.warning(
        request,
        _("%(title)s: %(count)s %(label)s(s).")
        % {
            "title": _translate_runtime_message(title),
            "count": len(entries),
            "label": _translate_runtime_message(label),
        },
    )
    for message in entries[:MAX_IMPORT_MESSAGES]:
        messages.warning(request, _translate_runtime_message(message))


def _notify_import_result(request, *, title, created, updated, errors, warnings):
    _add_limited_message_list(request, title=title, entries=errors, label=_("erreur"))
    _add_limited_message_list(request, title=title, entries=warnings, label=_("alerte"))
    messages.success(
        request,
        _("%(title)s: %(created)s créé(s), %(updated)s maj.")
        % {
            "title": _translate_runtime_message(title),
            "created": created,
            "updated": updated,
        },
    )


def _normalize_product_import_result(result):
    if len(result) < 4:
        raise ValueError("Résultat import produit invalide.")
    created, updated, errors, warnings = result[:4]
    stats = result[4] if len(result) > 4 and isinstance(result[4], dict) else {}
    if "distinct_products" not in stats:
        stats["distinct_products"] = created + updated
    if "temp_location_rows" not in stats:
        stats["temp_location_rows"] = 0
    return created, updated, errors, warnings, stats


def _notify_product_import_result(
    request,
    *,
    title,
    created,
    updated,
    errors,
    warnings,
    stats,
):
    _add_limited_message_list(request, title=title, entries=errors, label=_("erreur"))
    _add_limited_message_list(request, title=title, entries=warnings, label=_("alerte"))
    distinct_products = stats.get("distinct_products", created + updated)
    temp_location_rows = stats.get("temp_location_rows", 0)
    messages.success(
        request,
        _(
            "%(title)s: %(created)s créé(s), %(updated)s ligne(s) maj., "
            "%(distinct_products)s produit(s) distinct(s) impacté(s), "
            "%(temp_location_rows)s ligne(s) envoyée(s) vers TEMP."
        )
        % {
            "title": _translate_runtime_message(title),
            "created": created,
            "updated": updated,
            "distinct_products": distinct_products,
            "temp_location_rows": temp_location_rows,
        },
    )


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
        match_ids = [str(match_id_value) for match_id_value in item.get("match_ids", [])]
        if not match_id and len(match_ids) == 1:
            match_id = match_ids[0]
        if not match_id:
            messages.error(
                request,
                _("Import produit: sélection requise pour la mise à jour."),
            )
            return None
        if str(match_id) not in match_ids:
            messages.error(
                request,
                _("Import produit: produit cible invalide."),
            )
            return None
        decisions[row_index] = {
            "action": UPDATE_ACTION,
            "product_id": int(match_id),
        }
    return decisions


def _load_pending_rows(*, pending, clear_pending_import):
    if pending.get("source") != "file":
        return (
            pending.get("rows", []),
            None,
            pending.get("start_index", PRODUCT_IMPORT_START_INDEX_SINGLE),
        )

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
        matched, match_type = find_product_matches(sku=sku, name=name, brand=brand)
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
    quantity_mode=DEFAULT_QUANTITY_MODE,
    rows=None,
    temp_path=None,
    extension="",
):
    pending = {
        "token": uuid.uuid4().hex,
        "source": source,
        "start_index": start_index,
        "default_action": default_action,
        "quantity_mode": normalize_quantity_mode(quantity_mode),
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
        messages.error(request, _("Import produit: confirmation invalide."))
        return _redirect_scan_import()
    if request.POST.get("cancel"):
        clear_pending_import()
        messages.info(request, _("Import produit annule."))
        return _redirect_scan_import()

    decisions = _build_pending_decisions(request, pending)
    if decisions is None:
        return _redirect_scan_import()

    rows, base_dir, start_index = _load_pending_rows(
        pending=pending,
        clear_pending_import=clear_pending_import,
    )
    if rows is None:
        messages.error(request, _("Import produit: fichier temporaire introuvable."))
        return _redirect_scan_import()

    result = import_products_rows(
        rows,
        user=request.user,
        decisions=decisions,
        base_dir=base_dir,
        start_index=start_index,
        quantity_mode=normalize_quantity_mode(pending.get("quantity_mode")),
        collect_stats=True,
    )
    created, updated, errors, warnings, stats = _normalize_product_import_result(result)
    clear_pending_import()
    _notify_product_import_result(
        request,
        title=_("Import produits"),
        created=created,
        updated=updated,
        errors=errors,
        warnings=warnings,
        stats=stats,
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
        messages.error(request, _translate_runtime_message(errors[0]))
    else:
        for message in warnings[:MAX_IMPORT_MESSAGES]:
            messages.warning(request, _translate_runtime_message(message))
        messages.success(request, _("Produit créé."))
    return _redirect_scan_import()


def _handle_product_file_action(request):
    uploaded = request.FILES.get("import_file")
    update_existing = bool(request.POST.get("update_existing"))
    quantity_mode = normalize_quantity_mode(request.POST.get(PRODUCT_STOCK_MODE_FIELD))
    if not uploaded:
        messages.error(request, _("Fichier requis pour importer les produits."))
        return _redirect_scan_import()

    extension, data = _read_product_file_upload(uploaded)
    if _unsupported_product_extension(extension):
        messages.error(request, _("Format non supporte. Utilisez CSV/XLS/XLSX."))
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
            quantity_mode=quantity_mode,
            matches=matches,
        )
        _set_pending_import(request, pending)
        return render_scan_import(request, pending)

    result = import_products_rows(
        rows,
        user=request.user,
        base_dir=Path(temp_path).parent,
        start_index=PRODUCT_IMPORT_START_INDEX_FILE,
        quantity_mode=quantity_mode,
        collect_stats=True,
    )
    created, updated, errors, warnings, stats = _normalize_product_import_result(result)
    Path(temp_path).unlink(missing_ok=True)
    _notify_product_import_result(
        request,
        title=_("Import produits"),
        created=created,
        updated=updated,
        errors=errors,
        warnings=warnings,
        stats=stats,
    )
    return _redirect_scan_import()


def _handle_import_file_action(request, *, action, default_password):
    label, importer = IMPORT_FILE_ACTIONS[action]
    uploaded = request.FILES.get("import_file")
    if not uploaded:
        messages.error(
            request,
            _("Fichier requis pour importer les %(label)s.")
            % {"label": _translate_runtime_message(label)},
        )
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
        messages.error(
            request,
            _("Import %(label)s: %(message)s")
            % {
                "label": _translate_runtime_message(label),
                "message": _translate_runtime_message(exc),
            },
        )
        return _redirect_scan_import()

    created, updated, errors, warnings = normalize_import_result(result)
    _notify_import_result(
        request,
        title=_("Import %(label)s") % {"label": label},
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
        messages.error(
            request,
            _("Ajout %(label)s: %(message)s")
            % {
                "label": _translate_runtime_message(label),
                "message": _translate_runtime_message(exc),
            },
        )
        return _redirect_scan_import()

    created, updated, errors, warnings = normalize_import_result(result)
    if errors:
        messages.error(request, _translate_runtime_message(errors[0]))
    elif warnings:
        for message in warnings[:MAX_IMPORT_MESSAGES]:
            messages.warning(request, _translate_runtime_message(message))
    else:
        messages.success(
            request,
            _("%(label)s ajouté.") % {"label": _translate_runtime_message(label).capitalize()},
        )
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
