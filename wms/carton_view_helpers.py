from django.urls import reverse

from .models import CartonFormat, CartonStatus
from .scan_helpers import build_product_group_key, build_product_label


def get_carton_capacity_cm3():
    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    if not default_format:
        return None
    return (
        default_format.length_cm
        * default_format.width_cm
        * default_format.height_cm
    )


def build_cartons_ready_rows(cartons_qs, *, carton_capacity_cm3):
    cartons = []
    for carton in cartons_qs:
        product_totals = {}
        weight_total_g = 0
        volume_total_cm3 = 0
        missing_weight = False
        missing_volume = False
        for item in carton.cartonitem_set.all():
            product = item.product_lot.product
            lot_code = item.product_lot.lot_code
            key = build_product_group_key(product, lot_code)
            if key not in product_totals:
                product_totals[key] = {
                    "label": build_product_label(product, lot_code),
                    "quantity": 0,
                }
            product_totals[key]["quantity"] += item.quantity
            if product.weight_g:
                weight_total_g += product.weight_g * item.quantity
            else:
                missing_weight = True
            if product.volume_cm3:
                volume_total_cm3 += product.volume_cm3 * item.quantity
            else:
                missing_volume = True
        packing_list = sorted(
            product_totals.values(), key=lambda row: row["label"]
        )
        if weight_total_g == 0 and missing_weight:
            weight_kg = None
        else:
            weight_kg = weight_total_g / 1000 if weight_total_g else None
        if carton_capacity_cm3 and volume_total_cm3 and not missing_volume:
            volume_percent = round(
                float(volume_total_cm3) / float(carton_capacity_cm3) * 100
            )
        else:
            volume_percent = None
        is_assigned = carton.shipment_id is not None
        if is_assigned and carton.status != CartonStatus.SHIPPED:
            status_label = "Affecte"
        else:
            try:
                status_label = CartonStatus(carton.status).label
            except ValueError:
                status_label = carton.status
        if carton.shipment_id:
            packing_list_url = reverse(
                "scan:scan_shipment_carton_document",
                args=[carton.shipment_id, carton.id],
            )
        else:
            packing_list_url = reverse("scan:scan_carton_document", args=[carton.id])
        picking_url = reverse("scan:scan_carton_picking", args=[carton.id])
        cartons.append(
            {
                "id": carton.id,
                "code": carton.code,
                "created_at": carton.created_at,
                "status_label": status_label,
                "status_value": carton.status,
                "can_toggle": (not is_assigned)
                and carton.status != CartonStatus.SHIPPED,
                "shipment_reference": carton.shipment.reference if carton.shipment else "",
                "location": carton.current_location,
                "packing_list": packing_list,
                "packing_list_url": packing_list_url,
                "picking_url": picking_url,
                "weight_kg": weight_kg,
                "volume_percent": volume_percent,
            }
        )
    return cartons
