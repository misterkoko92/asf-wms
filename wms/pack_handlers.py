from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect

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
from .services import StockError, pack_carton


def build_pack_defaults(default_format):
    carton_format_id = (
        str(default_format.id) if default_format is not None else "custom"
    )
    carton_custom = {
        "length_cm": default_format.length_cm if default_format else Decimal("40"),
        "width_cm": default_format.width_cm if default_format else Decimal("30"),
        "height_cm": default_format.height_cm if default_format else Decimal("30"),
        "max_weight_g": default_format.max_weight_g if default_format else 8000,
    }
    line_count = 1
    line_values = build_pack_line_values(line_count)
    return carton_format_id, carton_custom, line_count, line_values


def handle_pack_post(request, *, form, default_format):
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
        carton_format_id = (
            str(default_format.id) if default_format is not None else "custom"
        )

    line_errors = {}
    line_items = []
    missing_defaults = []
    confirm_defaults = bool(request.POST.get("confirm_defaults"))

    if form.is_valid():
        shipment = resolve_shipment(form.cleaned_data["shipment_reference"])
        if form.cleaned_data["shipment_reference"] and not shipment:
            form.add_error("shipment_reference", "Expédition introuvable.")
        if carton_errors:
            for error in carton_errors:
                form.add_error(None, error)

        for index in range(1, line_count + 1):
            prefix = f"line_{index}_"
            product_code = (request.POST.get(prefix + "product_code") or "").strip()
            quantity_raw = (request.POST.get(prefix + "quantity") or "").strip()
            if not product_code and not quantity_raw:
                continue
            errors = []
            if not product_code:
                errors.append("Produit requis.")
            quantity = None
            if not quantity_raw:
                errors.append("Quantité requise.")
            else:
                quantity = parse_int(quantity_raw)
                if quantity is None or quantity <= 0:
                    errors.append("Quantité invalide.")
            product = (
                resolve_product(product_code, include_kits=True)
                if product_code
                else None
            )
            if product_code and not product:
                errors.append("Produit introuvable.")
            if errors:
                line_errors[str(index)] = errors
            else:
                line_items.append(
                    {"product": product, "quantity": quantity, "index": index}
                )

        if form.is_valid() and not line_errors and not carton_errors:
            if not line_items:
                form.add_error(None, "Ajoutez au moins un produit.")
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
                        "Attention : les produits suivants n'ont pas de dimensions "
                        "ni de poids enregistrés : "
                        f"{product_list}. Si vous validez ces ajouts, des valeurs "
                        "par défaut seront appliquées (1cm x 1cm x 1cm et 5g).",
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
                bins, pack_errors, pack_warnings = build_packing_bins(
                    line_items, carton_size, apply_defaults=confirm_defaults
                )
                if pack_errors:
                    for error in pack_errors:
                        form.add_error(None, error)
                else:
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
                                        current_location=form.cleaned_data[
                                            "current_location"
                                        ],
                                        carton_size=carton_size,
                                    )
                                if carton:
                                    created_cartons.append(carton)
                        for warning in pack_warnings:
                            messages.warning(request, warning)
                        request.session["pack_results"] = [
                            carton.id for carton in created_cartons
                        ]
                        messages.success(
                            request, f"{len(created_cartons)} carton(s) préparé(s)."
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
