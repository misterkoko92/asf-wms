from __future__ import annotations

from django.db import transaction
from django.db.models import Sum

from wms.models import (
    PreparationReservation,
    PreparationReservationStatus,
    PreparationRun,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    Product,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
)
from wms.preparation.generation import generate_preparation_run
from wms.shipment_party_rules import normalize_party_contact_to_org

OPEN_PREPARATION_RUN_STATUSES = {
    PreparationRunStatus.DRAFT,
    PreparationRunStatus.GENERATED,
    PreparationRunStatus.FROZEN,
}


def _open_proposal_queryset():
    return PreparationShipmentProposal.objects.filter(
        run__status__in=OPEN_PREPARATION_RUN_STATUSES,
    ).exclude(
        status=PreparationShipmentProposalStatus.CONVERTED,
    )


def _mark_proposals_needs_recalc(*, proposals):
    proposal_ids = list(proposals.values_list("id", flat=True))
    if not proposal_ids:
        return 0
    updated = PreparationShipmentProposal.objects.filter(id__in=proposal_ids).update(
        status=PreparationShipmentProposalStatus.NEEDS_RECALC
    )
    preparation_carton_model = PreparationShipmentProposal._meta.get_field(
        "carton_proposals"
    ).related_model
    preparation_carton_model.objects.filter(shipment_proposal_id__in=proposal_ids).update(
        status=PreparationShipmentProposalStatus.NEEDS_RECALC
    )
    return updated


@transaction.atomic
def mark_open_preparation_runs_stale_for_shipment(*, shipment: Shipment):
    shipper_org = normalize_party_contact_to_org(shipment.shipper_contact_ref)
    recipient_org = normalize_party_contact_to_org(shipment.recipient_contact_ref)
    if shipment.destination_id is None or shipper_org is None or recipient_org is None:
        return 0

    proposals = _open_proposal_queryset().filter(
        destination_id=shipment.destination_id,
        shipper__organization=shipper_org,
        recipient_organization__organization=recipient_org,
    )
    return _mark_proposals_needs_recalc(proposals=proposals)


@transaction.atomic
def mark_open_preparation_runs_stale_for_stock(*, product: Product):
    active_reservations = PreparationReservation.objects.filter(
        status=PreparationReservationStatus.ACTIVE,
        carton_proposal__product=product,
        shipment_proposal__run__status__in=OPEN_PREPARATION_RUN_STATUSES,
    )
    reserved_total = active_reservations.aggregate(total=Sum("quantity"))["total"] or 0
    on_hand_total = product.productlot_set.aggregate(total=Sum("quantity_on_hand"))["total"] or 0
    if on_hand_total >= reserved_total:
        return 0

    proposals = (
        _open_proposal_queryset()
        .filter(
            carton_proposals__product=product,
            reservations__status=PreparationReservationStatus.ACTIVE,
        )
        .distinct()
    )
    return _mark_proposals_needs_recalc(proposals=proposals)


@transaction.atomic
def recalculate_preparation_run(
    *,
    run: PreparationRun,
    created_by,
    api_batch_loader=None,
    asf_shipper=None,
    include_unspecified=False,
    manual_reserve_quantities=None,
):
    inputs = run.parameter_snapshot.get("inputs") or {}
    shipper_ids = inputs.get("shipper_ids") or list(
        run.need_snapshots.values_list("shipper_id", flat=True).distinct()
    )
    destination_ids = inputs.get("destination_ids") or list(
        run.need_snapshots.values_list("destination_id", flat=True).distinct()
    )
    shippers = list(ShipmentShipper.objects.filter(id__in=shipper_ids).order_by("id"))
    destinations = list(
        ShipmentRecipientOrganization._meta.get_field("destination")
        .remote_field.model.objects.filter(id__in=destination_ids)
        .order_by("id")
    )

    new_run = PreparationRun.objects.create(
        parameter_set=run.parameter_set,
        created_by=created_by,
        target_equivalent_units=run.target_equivalent_units,
        target_shipment_count=run.target_shipment_count,
        target_shipment_size_units=run.target_shipment_size_units,
        min_shipment_size_units=run.min_shipment_size_units,
        max_shipment_size_units=run.max_shipment_size_units,
        flight_window_start=run.flight_window_start,
        flight_window_end=run.flight_window_end,
        notes=run.notes,
        status=PreparationRunStatus.DRAFT,
    )
    generate_preparation_run(
        run=new_run,
        shippers=shippers,
        destinations=destinations,
        api_batch_loader=api_batch_loader,
        asf_shipper=asf_shipper,
        include_unspecified=include_unspecified,
        manual_reserve_quantities=manual_reserve_quantities,
    )
    snapshot = dict(new_run.parameter_snapshot or {})
    snapshot["recalculated_from_run_id"] = run.id
    new_run.parameter_snapshot = snapshot
    new_run.save(update_fields=["parameter_snapshot", "updated_at"])
    return new_run
