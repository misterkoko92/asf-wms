from __future__ import annotations

from dataclasses import dataclass

from wms.models import (
    PreparationProposalSource,
    PreparationShipmentProposal,
    Shipment,
    ShipmentStatus,
)
from wms.recipient_product_preferences import (
    UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS,
    resolve_effective_recipient_product_preference,
)
from wms.shipment_party_rules import normalize_party_contact_to_org

ACTIVE_HISTORY_SHIPMENT_STATUSES = {
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
}


@dataclass(frozen=True)
class PreparationScoreResult:
    score: float
    excluded: bool
    preference_status: str
    remaining_need: int
    fairness_quantity: int
    reasons: list[str]


def _iter_shipment_item_rows(shipment):
    for carton in shipment.carton_set.prefetch_related(
        "cartonitem_set__product_lot__product__category__parent"
    ).all():
        for item in carton.cartonitem_set.all():
            yield item.product_lot.product, item.quantity


def _shipment_matches_scope(*, shipment, shipper, recipient_organization, destination):
    if shipment.destination_id != destination.id:
        return False
    shipment_shipper_org = normalize_party_contact_to_org(shipment.shipper_contact_ref)
    shipment_recipient_org = normalize_party_contact_to_org(shipment.recipient_contact_ref)
    return (
        shipment_shipper_org == shipper.organization
        and shipment_recipient_org == recipient_organization.organization
    )


def _category_key(*, product, category_level):
    category = getattr(product, "category", None)
    if category is None:
        return None
    if str(category_level).upper() == "L3":
        return category.id
    while category.parent_id:
        category = category.parent
    return category.id


def compute_remaining_need(
    *,
    shipper,
    recipient_organization,
    destination,
    product,
    target_equivalent_units,
):
    shipments = (
        Shipment.objects.filter(
            destination=destination,
            status__in=ACTIVE_HISTORY_SHIPMENT_STATUSES,
        )
        .select_related(
            "shipper_contact_ref__organization",
            "recipient_contact_ref__organization",
        )
        .prefetch_related("carton_set__cartonitem_set__product_lot__product")
        .order_by("id")
    )
    delivered_or_planned = 0
    for shipment in shipments:
        if not _shipment_matches_scope(
            shipment=shipment,
            shipper=shipper,
            recipient_organization=recipient_organization,
            destination=destination,
        ):
            continue
        for row_product, quantity in _iter_shipment_item_rows(shipment):
            if row_product == product:
                delivered_or_planned += quantity
    return max(0, int(target_equivalent_units or 0) - delivered_or_planned)


def compute_fairness_history_quantity(*, destination, product, category_level="L2"):
    tracked_shipments = PreparationShipmentProposal.objects.filter(
        converted_shipment__isnull=False,
        converted_shipment__destination=destination,
        converted_shipment__status__in=ACTIVE_HISTORY_SHIPMENT_STATUSES,
        source__in=[PreparationProposalSource.ASF_STOCK, PreparationProposalSource.MIXED],
    ).select_related("converted_shipment")
    product_key = _category_key(product=product, category_level=category_level)
    quantity = 0
    seen_shipment_ids = set()
    for proposal in tracked_shipments:
        shipment = proposal.converted_shipment
        if shipment is None or shipment.id in seen_shipment_ids:
            continue
        seen_shipment_ids.add(shipment.id)
        for row_product, row_quantity in _iter_shipment_item_rows(shipment):
            if _category_key(product=row_product, category_level=category_level) == product_key:
                quantity += row_quantity
    return quantity


def score_preparation_candidate(
    *,
    shipper,
    recipient_organization,
    destination,
    product,
    asf_shipper=None,
    asf_penalty=1.0,
    shipper_score_coefficient=1.0,
    include_unspecified=False,
    fairness_category_level="L2",
):
    preference = resolve_effective_recipient_product_preference(
        recipient_organization=recipient_organization,
        product=product,
    )
    if preference.status == UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS and not include_unspecified:
        return PreparationScoreResult(
            score=0.0,
            excluded=True,
            preference_status=preference.status,
            remaining_need=0,
            fairness_quantity=0,
            reasons=["unspecified excluded"],
        )
    if preference.status == "refused":
        return PreparationScoreResult(
            score=0.0,
            excluded=True,
            preference_status=preference.status,
            remaining_need=0,
            fairness_quantity=0,
            reasons=["refused preference"],
        )

    base_score = {
        "requested": 100.0,
        "allowed": 60.0,
        UNSPECIFIED_RECIPIENT_PREFERENCE_STATUS: 15.0,
    }[preference.status]
    target_quantity = preference.quantity_target or 0
    remaining_need = compute_remaining_need(
        shipper=shipper,
        recipient_organization=recipient_organization,
        destination=destination,
        product=product,
        target_equivalent_units=target_quantity,
    )
    fairness_quantity = compute_fairness_history_quantity(
        destination=destination,
        product=product,
        category_level=fairness_category_level,
    )
    score = (base_score + (remaining_need * 5.0) - fairness_quantity) * float(
        shipper_score_coefficient
    )
    reasons = [f"{preference.status} preference", f"remaining need {remaining_need}"]
    if fairness_quantity:
        reasons.append(f"fairness penalty {fairness_quantity}")
    if asf_shipper is not None and shipper.id == asf_shipper.id:
        score *= float(asf_penalty)
        reasons.append(f"asf penalty {asf_penalty}")
    return PreparationScoreResult(
        score=score,
        excluded=False,
        preference_status=preference.status,
        remaining_need=remaining_need,
        fairness_quantity=fairness_quantity,
        reasons=reasons,
    )
