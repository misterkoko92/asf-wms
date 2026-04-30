from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from .carton_activity import record_carton_volunteer_activity
from .carton_status_events import set_carton_status
from .domain.stock import ensure_carton_code
from .emailing import enqueue_email_safe, get_admin_emails, get_group_emails
from .models import (
    CartonFormat,
    CartonStatus,
    CartonVolunteerActivityAction,
    Destination,
    Location,
    Product,
    ProductCategory,
    Shipment,
)
from .scan_helpers import (
    build_pack_line_values,
    build_packing_bins,
    get_product_volume_cm3,
    get_product_weight_g,
    parse_int,
    resolve_carton_size,
    resolve_product,
    resolve_shipment,
    resolve_standard_carton_format_for_family,
)
from .scan_pack_helpers import (
    build_forced_carton_warnings,
    build_forced_packing_bins,
    parse_forced_carton_count,
)
from .scan_permissions import user_is_preparateur
from .services import StockError, pack_carton, receive_stock, unpack_carton
from .shipment_status import sync_shipment_ready_state

PREPARATEUR_FAMILY_MM = "MM"
PREPARATEUR_FAMILY_CN = "CN"
PREPARATEUR_ALLOWED_FAMILIES = (
    PREPARATEUR_FAMILY_MM,
    PREPARATEUR_FAMILY_CN,
)
PACK_ACTION_PREPARE_WITHOUT_CONDITIONING = "prepare_without_conditioning"
PACK_ACTION_PREPARE_AVAILABLE = "prepare_available"
DEPRECATED_PACK_ACTION_PREPARE_AVAILABLE_BATCH = "prepare_available_batch"
PACK_CARTON_PLAN_MODE_EXACT = "exact"
EXACT_CARTON_OUTPUT_AVAILABLE = "available"
EXACT_CARTON_OUTPUT_WITHOUT_CONDITIONING = "without_conditioning"
EXACT_CARTON_OUTPUT_MODES = {
    EXACT_CARTON_OUTPUT_AVAILABLE,
    EXACT_CARTON_OUTPUT_WITHOUT_CONDITIONING,
}
CARTON_DISTRIBUTION_MODE_AUTO = "auto"
CARTON_DISTRIBUTION_MODE_MANUAL = "manual"
DEPRECATED_FREE_BATCH_ACTION_ERROR = _(
    "Le mode batch colis libres a été remplacé par le nombre de colis manuel."
)
PREPARATEUR_LOCATION_LABELS = {
    PREPARATEUR_FAMILY_MM: "Colis Prets MM",
    PREPARATEUR_FAMILY_CN: "Colis Prets CN",
}
ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT = "Account_User_Validation"


def _normalize_pack_family(value):
    normalized = (value or "").strip().upper()
    if normalized in PREPARATEUR_ALLOWED_FAMILIES:
        return normalized
    return ""


def _resolve_selected_shipment(value):
    if isinstance(value, Shipment):
        return value
    return resolve_shipment(value)


def _get_product_root_category_name(product):
    category = getattr(product, "category", None)
    while category and category.parent_id:
        category = category.parent
    return (category.name or "").strip().upper() if category else ""


def _resolve_preparateur_pack_family(product, override):
    override_family = _normalize_pack_family(override)
    if override_family:
        return override_family
    root_category_name = _get_product_root_category_name(product)
    if root_category_name in PREPARATEUR_ALLOWED_FAMILIES:
        return root_category_name
    return ""


def _resolve_preparateur_location(label):
    matches = list(
        Location.objects.filter(
            Q(notes__iexact=label)
            | Q(zone__iexact=label)
            | Q(aisle__iexact=label)
            | Q(shelf__iexact=label)
        )
        .select_related("warehouse")
        .order_by("warehouse__name", "zone", "aisle", "shelf")
    )
    if not matches:
        raise ValueError(
            _("Configuration emplacement introuvable pour %(label)s.") % {"label": label}
        )
    if len(matches) > 1:
        raise ValueError(_("Configuration emplacement ambigue pour %(label)s.") % {"label": label})
    return matches[0]


def _resolve_preparateur_locations():
    return {
        family: _resolve_preparateur_location(label)
        for family, label in PREPARATEUR_LOCATION_LABELS.items()
    }


def _resolve_preparateur_root_category(family):
    return (
        ProductCategory.objects.filter(parent__isnull=True, name__iexact=family)
        .order_by("id")
        .first()
    )


def _carton_size_from_format(format_obj):
    if format_obj is None:
        return None
    return {
        "length_cm": format_obj.length_cm,
        "width_cm": format_obj.width_cm,
        "height_cm": format_obj.height_cm,
        "max_weight_g": format_obj.max_weight_g,
    }


def _resolve_carton_format_label(*, carton_format_id, default_format):
    if carton_format_id == "custom":
        return "Personnalisé"
    if carton_format_id:
        format_obj = CartonFormat.objects.filter(pk=carton_format_id).only("name").first()
        if format_obj is not None:
            return format_obj.name
    return default_format.name if default_format is not None else "Standard"


def notify_preparateur_product_review_needed(
    *,
    product,
    created_by,
    location,
    quantity,
    lot_code,
    expires_on,
):
    validation_group_name = getattr(
        settings,
        "ACCOUNT_REQUEST_VALIDATION_GROUP_NAME",
        ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT,
    )
    recipients = list(
        dict.fromkeys(
            [
                *get_admin_emails(),
                *get_group_emails(validation_group_name, require_staff=True),
            ]
        )
    )
    if not recipients:
        return False

    review_url = reverse("scan:scan_stock_update")
    expires_on_label = expires_on.isoformat() if expires_on else "-"
    created_by_label = getattr(created_by, "username", "") or str(created_by)
    message = "\n".join(
        [
            _("Un produit créé par un préparateur doit être revu."),
            "",
            _("Produit : %(name)s") % {"name": product.name},
            _("SKU : %(sku)s") % {"sku": product.sku},
            _("Famille racine : %(family)s") % {"family": _get_product_root_category_name(product)},
            _("Créé par : %(username)s") % {"username": created_by_label},
            _("Emplacement : %(location)s") % {"location": location},
            _("Quantité initiale : %(quantity)s") % {"quantity": quantity},
            _("Lot : %(lot)s") % {"lot": lot_code or "-"},
            _("Péremption : %(expires_on)s") % {"expires_on": expires_on_label},
            "",
            _("Revue produit : %(url)s") % {"url": review_url},
        ]
    )
    return enqueue_email_safe(
        subject=_("Revue produit requise : %(sku)s") % {"sku": product.sku},
        message=message,
        recipient=recipients,
        tags=["scan", "preparateur", "product_review"],
    )


def create_preparateur_unknown_product_from_pack(*, request, form, receive_initial_stock=True):
    if not form.is_valid():
        raise ValueError("Unknown product form is invalid.")

    family = form.cleaned_data["pack_family"]
    category = _resolve_preparateur_root_category(family)
    if category is None:
        raise StockError(_("Catégorie racine introuvable pour %(family)s.") % {"family": family})

    with transaction.atomic():
        product = Product.objects.create(
            sku=form.cleaned_data["sku"],
            name=form.cleaned_data["name"],
            brand=form.cleaned_data["brand"],
            barcode=form.cleaned_data["barcode"],
            ean=form.cleaned_data["ean"],
            category=category,
            default_location=form.cleaned_data["location"],
            length_cm=form.cleaned_data["length_cm"],
            width_cm=form.cleaned_data["width_cm"],
            height_cm=form.cleaned_data["height_cm"],
            weight_g=form.cleaned_data["weight_g"],
            volume_cm3=form.cleaned_data["volume_cm3"],
            notes=form.cleaned_data["notes"],
            is_incomplete=True,
        )
        if receive_initial_stock:
            receive_stock(
                user=request.user,
                product=product,
                quantity=form.cleaned_data["initial_quantity"],
                location=form.cleaned_data["location"],
                lot_code=form.cleaned_data["lot_code"],
                received_on=timezone.localdate(),
                expires_on=form.cleaned_data["expires_on"],
            )

    notify_preparateur_product_review_needed(
        product=product,
        created_by=request.user,
        location=form.cleaned_data["location"],
        quantity=form.cleaned_data["initial_quantity"],
        lot_code=form.cleaned_data["lot_code"],
        expires_on=form.cleaned_data["expires_on"],
    )
    return product


def _resolve_pack_action(request):
    action = (request.POST.get("action") or "").strip()
    if action == PACK_ACTION_PREPARE_AVAILABLE:
        return PACK_ACTION_PREPARE_AVAILABLE
    return PACK_ACTION_PREPARE_WITHOUT_CONDITIONING


def _add_exact_plan_error(errors, key, message):
    errors.setdefault(key, []).append(str(message))


def _resolve_exact_plan_destination(value, errors, key):
    value = (value or "").strip()
    if not value:
        return None
    destination_id = parse_int(value)
    if destination_id is None:
        _add_exact_plan_error(errors, key, _("Destination invalide."))
        return None
    destination = Destination.objects.filter(pk=destination_id, is_active=True).first()
    if destination is None:
        _add_exact_plan_error(errors, key, _("Destination introuvable."))
    return destination


def _resolve_exact_plan_location(value, errors, key):
    value = (value or "").strip()
    if not value:
        return None
    location_id = parse_int(value)
    if location_id is None:
        _add_exact_plan_error(errors, key, _("Emplacement invalide."))
        return None
    location = Location.objects.filter(pk=location_id).first()
    if location is None:
        _add_exact_plan_error(errors, key, _("Emplacement introuvable."))
    return location


def _resolve_exact_plan_carton_size(request, *, carton_index, default_format, errors):
    fallback_format_id = str(default_format.id) if default_format is not None else "custom"
    carton_format_id = (
        request.POST.get(f"carton_{carton_index}_carton_format_id")
        or request.POST.get("carton_format_id")
        or fallback_format_id
    ).strip()
    carton_size, carton_errors = resolve_carton_size(
        carton_format_id=carton_format_id,
        default_format=default_format,
        data=request.POST,
    )
    for error in carton_errors:
        _add_exact_plan_error(errors, f"carton_{carton_index}", error)
    return carton_format_id, carton_size


def parse_exact_carton_plan(request, *, default_format):
    errors = {}
    missing_defaults = []
    plan = []
    carton_count = parse_int(request.POST.get("carton_plan_count"))
    if carton_count is None or carton_count <= 0:
        _add_exact_plan_error(errors, "carton_plan", _("Ajoutez au moins un colis."))
        return plan, errors, missing_defaults

    missing_default_names = set()
    for carton_index in range(1, carton_count + 1):
        carton_key = f"carton_{carton_index}"
        output_mode = (
            request.POST.get(f"{carton_key}_output_mode") or EXACT_CARTON_OUTPUT_AVAILABLE
        ).strip()
        if output_mode not in EXACT_CARTON_OUTPUT_MODES:
            _add_exact_plan_error(errors, carton_key, _("Mode de sortie invalide."))
            output_mode = EXACT_CARTON_OUTPUT_AVAILABLE

        shipment_reference = (request.POST.get(f"{carton_key}_shipment_reference") or "").strip()
        shipment = _resolve_selected_shipment(shipment_reference) if shipment_reference else None
        if shipment_reference and shipment is None:
            _add_exact_plan_error(errors, carton_key, _("Expédition introuvable."))

        preassigned_destination = None
        if shipment is None:
            preassigned_destination = _resolve_exact_plan_destination(
                request.POST.get(f"{carton_key}_preassigned_destination"),
                errors,
                carton_key,
            )

        current_location = _resolve_exact_plan_location(
            request.POST.get(f"{carton_key}_current_location"),
            errors,
            carton_key,
        )
        carton_format_id, carton_size = _resolve_exact_plan_carton_size(
            request,
            carton_index=carton_index,
            default_format=default_format,
            errors=errors,
        )

        line_count = parse_int(request.POST.get(f"{carton_key}_line_count")) or 0
        if line_count <= 0:
            _add_exact_plan_error(errors, carton_key, _("Ajoutez au moins un produit."))

        line_items = []
        for line_index in range(1, line_count + 1):
            line_key = f"{carton_key}_line_{line_index}"
            prefix = f"{line_key}_"
            product_code = (request.POST.get(prefix + "product_code") or "").strip()
            quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
            expires_on_raw = (request.POST.get(prefix + "expires_on") or "").strip()
            if not product_code and not quantity_raw:
                continue
            if not product_code:
                _add_exact_plan_error(errors, line_key, _("Produit requis."))
            quantity = None
            if not quantity_raw:
                _add_exact_plan_error(errors, line_key, _("Quantité requise."))
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    _add_exact_plan_error(errors, line_key, _("Quantité invalide."))
            product = resolve_product(product_code, include_kits=True) if product_code else None
            if product_code and product is None:
                _add_exact_plan_error(errors, line_key, _("Produit introuvable."))
            expires_on = None
            if expires_on_raw:
                expires_on = parse_date(expires_on_raw)
                if expires_on is None:
                    _add_exact_plan_error(errors, line_key, _("Date de péremption invalide."))
            if product is not None and quantity is not None and quantity > 0:
                if (
                    get_product_weight_g(product) is None
                    and get_product_volume_cm3(product) is None
                ):
                    missing_default_names.add(product.name)
                line_items.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "expires_on": expires_on,
                        "index": line_index,
                        "pack_family_override": (
                            request.POST.get(prefix + "pack_family_override") or ""
                        ),
                    }
                )

        if not line_items:
            _add_exact_plan_error(errors, carton_key, _("Ajoutez au moins un produit."))

        plan.append(
            {
                "index": carton_index,
                "output_mode": output_mode,
                "shipment": shipment,
                "preassigned_destination": preassigned_destination,
                "current_location": current_location,
                "carton_format_id": carton_format_id,
                "carton_size": carton_size,
                "line_items": line_items,
            }
        )

    missing_defaults = sorted(missing_default_names)
    return plan, errors, missing_defaults


def _resolve_carton_distribution_mode(request):
    mode = (request.POST.get("carton_distribution_mode") or "").strip()
    if mode == CARTON_DISTRIBUTION_MODE_AUTO:
        return CARTON_DISTRIBUTION_MODE_AUTO
    if mode == CARTON_DISTRIBUTION_MODE_MANUAL:
        return CARTON_DISTRIBUTION_MODE_MANUAL
    return (
        CARTON_DISTRIBUTION_MODE_MANUAL
        if (request.POST.get("forced_carton_count") or "").strip()
        else CARTON_DISTRIBUTION_MODE_AUTO
    )


def _get_active_preparateur_volunteer(request):
    return getattr(request, "scan_active_volunteer", None)


def _resolve_ready_location_for_available_pack(line_items):
    families = {
        _resolve_preparateur_pack_family(item["product"], item.get("pack_family_override"))
        for item in line_items
        if item.get("product") is not None
    }
    families.discard("")
    if len(families) > 1:
        return (
            None,
            _("Plusieurs types MM/CN ont été détectés. Emplacement READY laissé vide."),
        )
    if not families:
        return (
            None,
            _("Type MM/CN impossible à déterminer. Emplacement READY laissé vide."),
        )
    locations_by_family = _resolve_preparateur_locations()
    return locations_by_family[next(iter(families))], ""


def _build_state(
    *,
    carton_format_id,
    carton_custom,
    line_count,
    line_values,
    line_errors,
    missing_defaults,
    confirm_defaults,
    forced_carton_count=None,
    carton_distribution_mode=None,
):
    if carton_distribution_mode is None:
        carton_distribution_mode = (
            CARTON_DISTRIBUTION_MODE_MANUAL
            if forced_carton_count
            else CARTON_DISTRIBUTION_MODE_AUTO
        )
    return {
        "carton_format_id": carton_format_id,
        "carton_custom": carton_custom,
        "line_count": line_count,
        "line_values": line_values,
        "line_errors": line_errors,
        "missing_defaults": missing_defaults,
        "confirm_defaults": confirm_defaults,
        "forced_carton_count": forced_carton_count,
        "carton_distribution_mode": carton_distribution_mode,
    }


def _build_carton_custom(default_format, carton):
    matched_format = None
    if (
        carton.length_cm is not None
        and carton.width_cm is not None
        and carton.height_cm is not None
    ):
        matched_format = (
            CartonFormat.objects.filter(
                length_cm=carton.length_cm,
                width_cm=carton.width_cm,
                height_cm=carton.height_cm,
            )
            .order_by("-is_default", "id")
            .first()
        )
    if matched_format is not None:
        return str(matched_format.id), {
            "length_cm": matched_format.length_cm,
            "width_cm": matched_format.width_cm,
            "height_cm": matched_format.height_cm,
            "max_weight_g": matched_format.max_weight_g,
        }
    carton_custom = {
        "length_cm": carton.length_cm
        if carton.length_cm is not None
        else (default_format.length_cm if default_format else Decimal("40")),
        "width_cm": carton.width_cm
        if carton.width_cm is not None
        else (default_format.width_cm if default_format else Decimal("30")),
        "height_cm": carton.height_cm
        if carton.height_cm is not None
        else (default_format.height_cm if default_format else Decimal("30")),
        "max_weight_g": default_format.max_weight_g if default_format else 8000,
    }
    return "custom", carton_custom


def _build_carton_edit_line_values(carton):
    family_override = _normalize_pack_family((carton.code or "").split("-", 1)[0])
    rows_by_product_id = {}
    ordered_product_ids = []
    for item in carton.cartonitem_set.select_related("product_lot__product").order_by(
        "product_lot__product__name",
        "product_lot__product__sku",
        "product_lot__lot_code",
        "id",
    ):
        product = item.product_lot.product
        row = rows_by_product_id.get(product.id)
        if row is None:
            row = {
                "product_code": product.sku or product.name or "",
                "quantity": 0,
                "expires_on": None,
                "pack_family_override": family_override,
            }
            rows_by_product_id[product.id] = row
            ordered_product_ids.append(product.id)
        row["quantity"] += item.quantity
        expires_on = item.display_expires_on or item.product_lot.expires_on
        if expires_on is not None:
            if row["expires_on"] is None:
                row["expires_on"] = expires_on
            else:
                row["expires_on"] = min(row["expires_on"], expires_on)
    line_values = []
    for product_id in ordered_product_ids:
        row = rows_by_product_id[product_id]
        line_values.append(
            {
                "product_code": row["product_code"],
                "quantity": str(row["quantity"]),
                "per_carton_quantity": "",
                "expires_on": row["expires_on"].isoformat() if row["expires_on"] else "",
                "pack_family_override": row["pack_family_override"],
            }
        )
    if line_values:
        return len(line_values), line_values
    return 1, build_pack_line_values(1)


def _finalize_preparateur_carton(*, carton, family, user):
    if carton.status != CartonStatus.PACKED:
        set_carton_status(
            carton=carton,
            new_status=CartonStatus.PACKED,
            reason="scan_pack_preparateur_ready",
            user=user,
        )
    ensure_carton_code(carton, type_code=family)
    if carton.shipment_id:
        sync_shipment_ready_state(carton.shipment)


def _handle_preparateur_pack(
    *,
    request,
    form,
    shipment,
    preassigned_destination,
    carton_size,
    carton_format_id,
    carton_custom,
    line_count,
    line_values,
    line_errors,
    line_items,
    missing_defaults,
    confirm_defaults,
    forced_carton_count,
):
    active_volunteer = _get_active_preparateur_volunteer(request)
    if active_volunteer is None:
        form.add_error(None, _("Choisissez un bénévole depuis l'accueil préparateur."))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )
    grouped_line_items = defaultdict(list)
    for item in line_items:
        family = _resolve_preparateur_pack_family(
            item["product"],
            item.get("pack_family_override"),
        )
        if not family:
            line_errors[str(item["index"])] = [
                _("Choisissez manuellement MM ou CN pour ce produit."),
            ]
            continue
        item["pack_family"] = family
        grouped_line_items[family].append(item)

    if line_errors:
        form.add_error(
            None,
            _("Choisissez manuellement MM ou CN pour les produits sans categorie racine MM/CN."),
        )
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )

    try:
        locations_by_family = _resolve_preparateur_locations()
    except ValueError as exc:
        form.add_error(None, str(exc))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )

    pack_errors = []
    pack_warnings = []
    packing_plan = []
    non_empty_families = [
        family for family in PREPARATEUR_ALLOWED_FAMILIES if grouped_line_items.get(family)
    ]
    force_applies = forced_carton_count and len(non_empty_families) == 1
    if forced_carton_count and len(non_empty_families) > 1:
        pack_warnings.append(
            _("Nombre de colis forcé non appliqué : plusieurs familles MM/CN ont été détectées.")
        )
    for family in PREPARATEUR_ALLOWED_FAMILIES:
        family_items = grouped_line_items.get(family, [])
        if not family_items:
            continue
        family_format = resolve_standard_carton_format_for_family(family)
        family_format_label = family_format.name if family_format is not None else "Standard"
        family_carton_size = _carton_size_from_format(family_format) or carton_size
        bins, family_errors, family_warnings = build_packing_bins(
            family_items,
            family_carton_size,
            apply_defaults=confirm_defaults,
        )
        pack_errors.extend(family_errors)
        pack_warnings.extend(family_warnings)
        if force_applies:
            forced_bins = build_forced_packing_bins(family_items, forced_carton_count)
            if forced_bins:
                if len(forced_bins) != len(bins or []):
                    pack_warnings.append(
                        _("Nombre de colis forcé: %(forced)s au lieu de %(auto)s.")
                        % {"forced": len(forced_bins), "auto": len(bins or [])}
                    )
                bins = forced_bins
                pack_warnings.extend(
                    build_forced_carton_warnings(
                        bins=bins,
                        carton_size=family_carton_size,
                        carton_format_label=family_format_label,
                    )
                )
        if bins:
            for bin_data in bins:
                packing_plan.append(
                    {
                        "family": family,
                        "zone_label": PREPARATEUR_LOCATION_LABELS[family],
                        "current_location": locations_by_family[family],
                        "carton_size": family_carton_size,
                        "bin_data": bin_data,
                    }
                )

    if pack_errors:
        for error in pack_errors:
            form.add_error(None, error)
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )

    try:
        created_cartons = []
        with transaction.atomic():
            for plan in packing_plan:
                carton = None
                for entry in plan["bin_data"]["items"].values():
                    carton = pack_carton(
                        user=request.user,
                        product=entry["product"],
                        quantity=entry["quantity"],
                        carton=carton,
                        carton_code=None,
                        shipment=shipment,
                        preassigned_destination=preassigned_destination,
                        display_expires_on=entry.get("expires_on"),
                        current_location=plan["current_location"],
                        carton_size=plan["carton_size"],
                        prepared_by_user=active_volunteer.user,
                        volunteer_profile=active_volunteer,
                        actor_user=request.user,
                    )
                if carton:
                    _finalize_preparateur_carton(
                        carton=carton,
                        family=plan["family"],
                        user=request.user,
                    )
                    created_cartons.append(
                        {
                            "carton_id": carton.id,
                            "zone_label": plan["zone_label"],
                            "family": plan["family"],
                        }
                    )
        for warning in pack_warnings:
            messages.warning(request, warning)
        request.session["pack_results"] = created_cartons
        messages.success(
            request,
            _("%(count)s carton(s) préparé(s).") % {"count": len(created_cartons)},
        )
        return (
            redirect("scan:scan_pack"),
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )
    except StockError as exc:
        form.add_error(None, str(exc))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
            ),
        )


def _handle_carton_edit_pack(
    *,
    request,
    form,
    editing_carton,
    shipment,
    preassigned_destination,
    carton_size,
    carton_format_id,
    carton_custom,
    line_count,
    line_values,
    line_errors,
    line_items,
    missing_defaults,
    confirm_defaults,
):
    bins, pack_errors, pack_warnings = build_packing_bins(
        line_items,
        carton_size,
        apply_defaults=confirm_defaults,
    )
    if pack_errors:
        for error in pack_errors:
            form.add_error(None, error)
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
            ),
        )
    if len(bins) != 1:
        form.add_error(None, _("Le carton modifié doit tenir dans un seul colis."))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
            ),
        )

    target_shipment = editing_carton.shipment if editing_carton.shipment_id else shipment
    target_preassigned_destination = (
        None if target_shipment is not None else preassigned_destination
    )
    target_location = form.cleaned_data["current_location"]
    if target_location is None and user_is_preparateur(request.user):
        target_location = editing_carton.current_location

    active_volunteer = (
        _get_active_preparateur_volunteer(request) if user_is_preparateur(request.user) else None
    )
    if user_is_preparateur(request.user) and active_volunteer is None:
        form.add_error(None, _("Choisissez un bénévole depuis l'accueil préparateur."))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
            ),
        )

    try:
        with transaction.atomic():
            if editing_carton.cartonitem_set.exists():
                unpack_carton(user=request.user, carton=editing_carton)
                editing_carton.refresh_from_db()
            for entry in bins[0]["items"].values():
                editing_carton = pack_carton(
                    user=request.user,
                    product=entry["product"],
                    quantity=entry["quantity"],
                    carton=editing_carton,
                    carton_code=None,
                    shipment=target_shipment,
                    preassigned_destination=target_preassigned_destination,
                    display_expires_on=entry.get("expires_on"),
                    current_location=target_location,
                    carton_size=carton_size,
                    prepared_by_user=active_volunteer.user
                    if active_volunteer is not None
                    else None,
                    volunteer_profile=active_volunteer,
                    actor_user=request.user,
                )
            if active_volunteer is not None:
                record_carton_volunteer_activity(
                    carton=editing_carton,
                    volunteer=active_volunteer,
                    action=CartonVolunteerActivityAction.EDITED,
                    actor=request.user,
                )
        for warning in pack_warnings:
            messages.warning(request, warning)
        messages.success(
            request,
            _("Colis %(code)s mis à jour.") % {"code": editing_carton.code},
        )
        return (
            redirect("scan:scan_cartons_ready"),
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
            ),
        )
    except StockError as exc:
        form.add_error(None, str(exc))
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
            ),
        )


def build_pack_defaults(default_format, *, carton=None):
    if carton is None:
        carton_format_id = str(default_format.id) if default_format is not None else "custom"
        carton_custom = {
            "length_cm": default_format.length_cm if default_format else Decimal("40"),
            "width_cm": default_format.width_cm if default_format else Decimal("30"),
            "height_cm": default_format.height_cm if default_format else Decimal("30"),
            "max_weight_g": default_format.max_weight_g if default_format else 8000,
        }
        line_count = 1
        line_values = build_pack_line_values(line_count)
        return carton_format_id, carton_custom, line_count, line_values, None
    carton_format_id, carton_custom = _build_carton_custom(default_format, carton)
    line_count, line_values = _build_carton_edit_line_values(carton)
    return carton_format_id, carton_custom, line_count, line_values, None


def handle_pack_post(request, *, form, default_format, editing_carton=None):
    carton_format_id = (request.POST.get("carton_format_id") or "").strip()
    carton_custom = {
        "length_cm": request.POST.get("carton_length_cm", ""),
        "width_cm": request.POST.get("carton_width_cm", ""),
        "height_cm": request.POST.get("carton_height_cm", ""),
        "max_weight_g": request.POST.get("carton_max_weight_g", ""),
    }
    line_count = parse_int(request.POST.get("line_count")) or 1
    line_count = max(1, line_count)
    line_values = build_pack_line_values(line_count, request.POST)
    carton_size, carton_errors = resolve_carton_size(
        carton_format_id=carton_format_id,
        default_format=default_format,
        data=request.POST,
    )
    if not carton_format_id:
        carton_format_id = str(default_format.id) if default_format is not None else "custom"

    line_errors = {}
    line_items = []
    missing_defaults = []
    confirm_defaults = bool(request.POST.get("confirm_defaults"))
    pack_action = _resolve_pack_action(request)
    deprecated_free_batch_requested = (
        request.POST.get("action") or ""
    ).strip() == DEPRECATED_PACK_ACTION_PREPARE_AVAILABLE_BATCH
    carton_distribution_mode = _resolve_carton_distribution_mode(request)
    forced_carton_error = None
    try:
        forced_carton_count = (
            None
            if editing_carton is not None
            or carton_distribution_mode == CARTON_DISTRIBUTION_MODE_AUTO
            else parse_forced_carton_count(request.POST.get("forced_carton_count"))
        )
    except ValueError as exc:
        forced_carton_count = None
        forced_carton_error = str(exc)
        form.add_error(None, forced_carton_error)
    shipment = None

    if deprecated_free_batch_requested:
        form.add_error(None, DEPRECATED_FREE_BATCH_ACTION_ERROR)
        return (
            None,
            _build_state(
                carton_format_id=carton_format_id,
                carton_custom=carton_custom,
                line_count=line_count,
                line_values=line_values,
                line_errors=line_errors,
                missing_defaults=missing_defaults,
                confirm_defaults=confirm_defaults,
                forced_carton_count=forced_carton_count,
                carton_distribution_mode=carton_distribution_mode,
            ),
        )

    if form.is_valid() and forced_carton_error is None:
        shipment = (
            editing_carton.shipment
            if editing_carton is not None and editing_carton.shipment_id
            else _resolve_selected_shipment(form.cleaned_data["shipment_reference"])
        )
        preassigned_destination = (
            None if shipment is not None else form.cleaned_data["preassigned_destination"]
        )
        if (
            (editing_carton is None or editing_carton.shipment_id is None)
            and form.cleaned_data["shipment_reference"]
            and not shipment
        ):
            form.add_error("shipment_reference", _("Expédition introuvable."))
        if carton_errors:
            for error in carton_errors:
                form.add_error(None, error)

        for index in range(1, line_count + 1):
            prefix = f"line_{index}_"
            product_code = (request.POST.get(prefix + "product_code") or "").strip()
            quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
            expires_on_raw = (request.POST.get(prefix + "expires_on") or "").strip()
            if not product_code and not quantity_raw:
                continue
            errors = []
            if not product_code:
                errors.append(_("Produit requis."))
            quantity = None
            if not quantity_raw:
                errors.append(_("Quantité requise."))
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    errors.append(_("Quantité invalide."))
            product = resolve_product(product_code, include_kits=True) if product_code else None
            if product_code and not product:
                errors.append(_("Produit introuvable."))
            expires_on = None
            if expires_on_raw:
                expires_on = parse_date(expires_on_raw)
                if expires_on is None:
                    errors.append(_("Date de péremption invalide."))
            if errors:
                line_errors[str(index)] = errors
            else:
                line_items.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "expires_on": expires_on,
                        "index": index,
                        "pack_family_override": (
                            request.POST.get(prefix + "pack_family_override") or ""
                        ),
                    }
                )

        if form.is_valid() and not line_errors and not carton_errors:
            if not line_items:
                form.add_error(None, _("Ajoutez au moins un produit."))
            else:
                missing_defaults = sorted(
                    {
                        item["product"].name
                        for item in line_items
                        if get_product_weight_g(item["product"]) is None
                        and get_product_volume_cm3(item["product"]) is None
                    }
                )
                if missing_defaults and not confirm_defaults:
                    product_list = ", ".join(missing_defaults)
                    form.add_error(
                        None,
                        _(
                            "Attention : les produits suivants n'ont pas de dimensions "
                            "ni de poids enregistrés : %(products)s. Si vous validez "
                            "ces ajouts, des valeurs par défaut seront appliquées "
                            "(1cm x 1cm x 1cm et 5g)."
                        )
                        % {"products": product_list},
                    )
                    return (
                        None,
                        {
                            "carton_format_id": carton_format_id,
                            "carton_custom": carton_custom,
                            "line_count": line_count,
                            "line_values": line_values,
                            "line_errors": line_errors,
                            "missing_defaults": missing_defaults,
                            "confirm_defaults": confirm_defaults,
                            "forced_carton_count": forced_carton_count,
                            "carton_distribution_mode": carton_distribution_mode,
                        },
                    )
                if user_is_preparateur(request.user):
                    if editing_carton is not None:
                        return _handle_carton_edit_pack(
                            request=request,
                            form=form,
                            editing_carton=editing_carton,
                            shipment=shipment,
                            preassigned_destination=preassigned_destination,
                            carton_size=carton_size,
                            carton_format_id=carton_format_id,
                            carton_custom=carton_custom,
                            line_count=line_count,
                            line_values=line_values,
                            line_errors=line_errors,
                            line_items=line_items,
                            missing_defaults=missing_defaults,
                            confirm_defaults=confirm_defaults,
                        )
                    return _handle_preparateur_pack(
                        request=request,
                        form=form,
                        shipment=shipment,
                        preassigned_destination=preassigned_destination,
                        carton_size=carton_size,
                        carton_format_id=carton_format_id,
                        carton_custom=carton_custom,
                        line_count=line_count,
                        line_values=line_values,
                        line_errors=line_errors,
                        line_items=line_items,
                        missing_defaults=missing_defaults,
                        confirm_defaults=confirm_defaults,
                        forced_carton_count=forced_carton_count,
                    )
                if editing_carton is not None:
                    return _handle_carton_edit_pack(
                        request=request,
                        form=form,
                        editing_carton=editing_carton,
                        shipment=shipment,
                        preassigned_destination=preassigned_destination,
                        carton_size=carton_size,
                        carton_format_id=carton_format_id,
                        carton_custom=carton_custom,
                        line_count=line_count,
                        line_values=line_values,
                        line_errors=line_errors,
                        line_items=line_items,
                        missing_defaults=missing_defaults,
                        confirm_defaults=confirm_defaults,
                    )
                if pack_action == PACK_ACTION_PREPARE_AVAILABLE and shipment is not None:
                    form.add_error(
                        "shipment_reference",
                        _("Retirez la référence d'expédition pour mettre les colis en disponible."),
                    )
                    return (
                        None,
                        _build_state(
                            carton_format_id=carton_format_id,
                            carton_custom=carton_custom,
                            line_count=line_count,
                            line_values=line_values,
                            line_errors=line_errors,
                            missing_defaults=missing_defaults,
                            confirm_defaults=confirm_defaults,
                            forced_carton_count=forced_carton_count,
                            carton_distribution_mode=carton_distribution_mode,
                        ),
                    )
                bins, pack_errors, pack_warnings = build_packing_bins(
                    line_items, carton_size, apply_defaults=confirm_defaults
                )
                if pack_errors:
                    for error in pack_errors:
                        form.add_error(None, error)
                else:
                    if forced_carton_count:
                        forced_bins = build_forced_packing_bins(line_items, forced_carton_count)
                        if forced_bins:
                            if len(forced_bins) != len(bins or []):
                                pack_warnings.append(
                                    _("Nombre de colis forcé: %(forced)s au lieu de %(auto)s.")
                                    % {"forced": len(forced_bins), "auto": len(bins or [])}
                                )
                            bins = forced_bins
                            pack_warnings.extend(
                                build_forced_carton_warnings(
                                    bins=bins,
                                    carton_size=carton_size,
                                    carton_format_label=_resolve_carton_format_label(
                                        carton_format_id=carton_format_id,
                                        default_format=default_format,
                                    ),
                                )
                            )
                    current_location = form.cleaned_data["current_location"]
                    ready_location_warning = ""
                    skip_picking_status = False
                    if pack_action == PACK_ACTION_PREPARE_AVAILABLE:
                        try:
                            current_location, ready_location_warning = (
                                _resolve_ready_location_for_available_pack(line_items)
                            )
                        except ValueError as exc:
                            form.add_error(None, str(exc))
                            return (
                                None,
                                _build_state(
                                    carton_format_id=carton_format_id,
                                    carton_custom=carton_custom,
                                    line_count=line_count,
                                    line_values=line_values,
                                    line_errors=line_errors,
                                    missing_defaults=missing_defaults,
                                    confirm_defaults=confirm_defaults,
                                    forced_carton_count=forced_carton_count,
                                    carton_distribution_mode=carton_distribution_mode,
                                ),
                            )
                        skip_picking_status = True
                    try:
                        created_cartons = []
                        with transaction.atomic():
                            for bin_data in bins:
                                carton = None
                                for entry in bin_data["items"].values():
                                    carton = pack_carton(
                                        user=request.user,
                                        product=entry["product"],
                                        quantity=entry["quantity"],
                                        carton=carton,
                                        carton_code=None,
                                        shipment=shipment,
                                        preassigned_destination=preassigned_destination,
                                        display_expires_on=entry.get("expires_on"),
                                        current_location=current_location,
                                        carton_size=carton_size,
                                        skip_picking_status=skip_picking_status,
                                    )
                                if carton:
                                    if pack_action == PACK_ACTION_PREPARE_AVAILABLE:
                                        set_carton_status(
                                            carton=carton,
                                            new_status=CartonStatus.PACKED,
                                            reason="scan_pack_mark_ready",
                                            user=request.user,
                                        )
                                    created_cartons.append(carton)
                        if ready_location_warning:
                            messages.warning(request, ready_location_warning)
                        for warning in pack_warnings:
                            messages.warning(request, warning)
                        request.session["pack_results"] = [carton.id for carton in created_cartons]
                        messages.success(
                            request,
                            (
                                _("%(count)s carton(s) préparé(s) et mis en disponible.")
                                if pack_action == PACK_ACTION_PREPARE_AVAILABLE
                                else _("%(count)s carton(s) préparé(s).")
                            )
                            % {"count": len(created_cartons)},
                        )
                        return (
                            redirect("scan:scan_pack"),
                            {
                                "carton_format_id": carton_format_id,
                                "carton_custom": carton_custom,
                                "line_count": line_count,
                                "line_values": line_values,
                                "line_errors": line_errors,
                                "missing_defaults": missing_defaults,
                                "confirm_defaults": confirm_defaults,
                                "forced_carton_count": forced_carton_count,
                                "carton_distribution_mode": carton_distribution_mode,
                            },
                        )
                    except StockError as exc:
                        form.add_error(None, str(exc))

    return (
        None,
        _build_state(
            carton_format_id=carton_format_id,
            carton_custom=carton_custom,
            line_count=line_count,
            line_values=line_values,
            line_errors=line_errors,
            missing_defaults=missing_defaults,
            confirm_defaults=confirm_defaults,
            forced_carton_count=forced_carton_count,
            carton_distribution_mode=carton_distribution_mode,
        ),
    )
