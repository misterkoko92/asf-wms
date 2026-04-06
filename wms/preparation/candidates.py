from __future__ import annotations

from dataclasses import dataclass

from wms.models import Carton
from wms.preparation.reservations import compute_run_usable_stock
from wms.shipment_party_rules import normalize_party_contact_to_org


@dataclass(frozen=True)
class PreparationCandidate:
    source: str
    quantity: int
    products: list[dict]
    carton: object | None = None
    shipment: object | None = None
    product: object | None = None


def _carton_products(carton):
    products = []
    for item in carton.cartonitem_set.select_related("product_lot__product").all():
        products.append(
            {
                "product": item.product_lot.product,
                "quantity": item.quantity,
            }
        )
    return products


def build_deposited_carton_candidates(*, shipper, recipient_organization, destination):
    cart_queryset = (
        Carton.objects.filter(
            shipment__isnull=False,
            shipment__destination=destination,
        )
        .select_related(
            "shipment",
            "shipment__shipper_contact_ref__organization",
            "shipment__recipient_contact_ref__organization",
        )
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("id")
    )
    candidates = []
    expected_shipper_org = shipper.organization
    expected_recipient_org = recipient_organization.organization
    for carton in cart_queryset:
        shipment = carton.shipment
        if shipment is None:
            continue
        shipment_shipper_org = normalize_party_contact_to_org(shipment.shipper_contact_ref)
        shipment_recipient_org = normalize_party_contact_to_org(shipment.recipient_contact_ref)
        if shipment_shipper_org != expected_shipper_org:
            continue
        if shipment_recipient_org != expected_recipient_org:
            continue
        products = _carton_products(carton)
        candidates.append(
            PreparationCandidate(
                source="deposit",
                carton=carton,
                shipment=shipment,
                product=None,
                quantity=sum(entry["quantity"] for entry in products),
                products=products,
            )
        )
    return candidates


def build_asf_stock_carton_candidates(*, product, manual_reserve_quantity=0):
    usable_quantity = compute_run_usable_stock(
        product=product,
        manual_reserve_quantity=manual_reserve_quantity,
    )
    if usable_quantity <= 0:
        return []
    return [
        PreparationCandidate(
            source="asf_stock",
            carton=None,
            shipment=None,
            product=product,
            quantity=usable_quantity,
            products=[{"product": product, "quantity": usable_quantity}],
        )
    ]


def build_mixed_carton_candidates(*, deposited_candidates, stock_candidates):
    return [*deposited_candidates, *stock_candidates]
