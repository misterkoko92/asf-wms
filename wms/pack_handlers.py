from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _

from .carton_status_events import set_carton_status
from .domain.stock import ensure_carton_code
from .models import CartonFormat, CartonStatus, Location
from .scan_helpers import (
    build_pack_line_values,
    build_packing_bins,
    get_product_volume_cm3,
    get_product_weight_g,
    parse_int,
    resolve_carton_size,
    resolve_product,
    resolve_shipment,
)
from .scan_permissions import user_is_preparateur
from .services import StockError, pack_carton, unpack_carton
from .shipment_status import sync_shipment_ready_state

PREPARATEUR_FAMILY_MM = "MM"
PREPARATEUR_FAMILY_CN = "CN"
PREPARATEUR_ALLOWED_FAMILIES = (
    PREPARATEUR_FAMILY_MM,
    PREPARATEUR_FAMILY_CN,
)
PACK_ACTION_PREPARE_WITHOUT_CONDITIONING = "prepare_without_conditioning"
PACK_ACTION_PREPARE_AVAILABLE = "prepare_available"
PREPARATEUR_LOCATION_LABELS = {
    PREPARATEUR_FAMILY_MM: "Colis Prets MM",
    PREPARATEUR_FAMILY_CN: "Colis Prets CN",
}


def _normalize_pack_family(value):
    normalized = (value or "").strip().upper()
    if normalized in PREPARATEUR_ALLOWED_FAMILIES:
        return normalized
    return ""


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


def _resolve_pack_action(request):
    action = (request.POST.get("action") or "").strip()
    if action == PACK_ACTION_PREPARE_AVAILABLE:
        return PACK_ACTION_PREPARE_AVAILABLE
    return PACK_ACTION_PREPARE_WITHOUT_CONDITIONING


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
):
    return {
        "carton_format_id": carton_format_id,
        "carton_custom": carton_custom,
        "line_count": line_count,
        "line_values": line_values,
        "line_errors": line_errors,
        "missing_defaults": missing_defaults,
        "confirm_defaults": confirm_defaults,
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
):
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
            ),
        )

    pack_errors = []
    pack_warnings = []
    packing_plan = []
    for family in PREPARATEUR_ALLOWED_FAMILIES:
        family_items = grouped_line_items.get(family, [])
        if not family_items:
            continue
        bins, family_errors, family_warnings = build_packing_bins(
            family_items,
            carton_size,
            apply_defaults=confirm_defaults,
        )
        pack_errors.extend(family_errors)
        pack_warnings.extend(family_warnings)
        if bins:
            for bin_data in bins:
                packing_plan.append(
                    {
                        "family": family,
                        "zone_label": PREPARATEUR_LOCATION_LABELS[family],
                        "current_location": locations_by_family[family],
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
                        carton_size=carton_size,
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
        return carton_format_id, carton_custom, line_count, line_values
    carton_format_id, carton_custom = _build_carton_custom(default_format, carton)
    line_count, line_values = _build_carton_edit_line_values(carton)
    return carton_format_id, carton_custom, line_count, line_values


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
    shipment = None
    pack_action = _resolve_pack_action(request)

    if form.is_valid():
        shipment = (
            editing_carton.shipment
            if editing_carton is not None and editing_carton.shipment_id
            else resolve_shipment(form.cleaned_data["shipment_reference"])
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
                        ),
                    )
                bins, pack_errors, pack_warnings = build_packing_bins(
                    line_items, carton_size, apply_defaults=confirm_defaults
                )
                if pack_errors:
                    for error in pack_errors:
                        form.add_error(None, error)
                else:
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
        ),
    )
