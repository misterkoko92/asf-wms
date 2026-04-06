from __future__ import annotations

from django.db import transaction

from wms.carton_status_events import set_carton_status
from wms.domain.stock import StockError, _prepare_carton, ensure_carton_code
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    MovementType,
    PreparationProposalSource,
    PreparationReservationStatus,
    PreparationRunStatus,
    PreparationShipmentProposalStatus,
    Shipment,
    ShipmentStatus,
    StockMovement,
)
from wms.preparation.review import carton_is_deleted, proposal_is_deleted
from wms.shipment_helpers import (
    build_destination_label,
    shipment_correspondent_contact_for_destination,
)
from wms.shipment_party_snapshot import build_shipment_party_snapshot_payload
from wms.shipment_status import sync_shipment_ready_state


def _build_shipment_for_proposal(*, proposal, created_by):
    shipper_contact = proposal.shipper.organization
    recipient_contact = proposal.recipient_organization.organization
    destination = proposal.destination

    correspondent_contact = shipment_correspondent_contact_for_destination(destination)
    if correspondent_contact is None:
        fallback_correspondent = getattr(destination, "correspondent_contact", None)
        if fallback_correspondent is not None and fallback_correspondent.is_active:
            correspondent_contact = fallback_correspondent

    shipper_name = shipper_contact.name
    recipient_name = recipient_contact.name
    correspondent_name = correspondent_contact.name if correspondent_contact is not None else ""
    party_payload = build_shipment_party_snapshot_payload(
        shipper_contact=shipper_contact,
        recipient_contact=recipient_contact,
        correspondent_contact=correspondent_contact,
        shipper_name=shipper_name,
        recipient_name=recipient_name,
        correspondent_name=correspondent_name,
    )
    return Shipment.objects.create(
        status=ShipmentStatus.PICKING,
        shipper_name=shipper_name,
        shipper_contact_ref=shipper_contact,
        shipper_contact=shipper_name,
        recipient_name=recipient_name,
        recipient_contact_ref=recipient_contact,
        recipient_contact=recipient_name,
        correspondent_name=correspondent_name,
        correspondent_contact_ref=correspondent_contact,
        destination=destination,
        destination_address=build_destination_label(destination),
        destination_country=destination.country,
        created_by=created_by,
        **party_payload,
    )


def _pack_carton_from_preparation_reservations(*, carton_proposal, shipment, user):
    reservations = list(
        carton_proposal.reservations.filter(status=PreparationReservationStatus.ACTIVE)
        .select_related("product_lot", "product_lot__product", "product_lot__location")
        .order_by("product_lot__expires_on", "product_lot__received_on", "product_lot__id")
    )
    if not reservations:
        raise StockError("Réservation active requise pour convertir le colis.")

    carton = _prepare_carton(
        user=user,
        carton=None,
        shipment=shipment,
        current_location=getattr(carton_proposal.product, "default_location", None),
    )
    for reservation in reservations:
        lot = reservation.product_lot
        quantity = reservation.quantity
        if quantity <= 0:
            continue
        lot.quantity_reserved = max(0, lot.quantity_reserved - quantity)
        lot.quantity_on_hand = max(0, lot.quantity_on_hand - quantity)
        lot.save(update_fields=["quantity_reserved", "quantity_on_hand"])
        StockMovement.objects.create(
            movement_type=MovementType.OUT,
            product=lot.product,
            product_lot=lot,
            quantity=quantity,
            from_location=lot.location,
            related_carton=carton,
            related_shipment=shipment,
            created_by=user,
        )
        item, _created = CartonItem.objects.get_or_create(
            carton=carton,
            product_lot=lot,
            defaults={"quantity": 0},
        )
        item.quantity += quantity
        item.save(update_fields=["quantity"])
        reservation.status = PreparationReservationStatus.CONSUMED
        reservation.save(update_fields=["status"])

    if carton.status != CartonStatus.ASSIGNED:
        set_carton_status(
            carton=carton,
            new_status=CartonStatus.ASSIGNED,
            reason="preparation_run_assign",
            user=user,
        )
    sync_shipment_ready_state(shipment)
    ensure_carton_code(carton)
    return carton


def _reassign_deposit_carton(*, carton_proposal, shipment, user):
    source_carton_id = (carton_proposal.rationale or {}).get("source_carton_id")
    if not source_carton_id:
        raise StockError("Carton source requis pour convertir un dépôt.")
    carton = Carton.objects.filter(pk=source_carton_id).select_related("shipment").first()
    if carton is None:
        raise StockError("Carton source introuvable.")
    if carton.status == CartonStatus.SHIPPED:
        raise StockError("Impossible de réaffecter un carton expédié.")

    previous_shipment = carton.shipment
    carton.shipment = shipment
    carton.preassigned_destination = None
    set_carton_status(
        carton=carton,
        new_status=CartonStatus.ASSIGNED,
        reason="preparation_run_reassign",
        user=user,
        update_fields=["shipment", "preassigned_destination"],
    )
    if previous_shipment is not None and previous_shipment.id != shipment.id:
        sync_shipment_ready_state(previous_shipment)
    sync_shipment_ready_state(shipment)
    return carton


def _convert_carton_proposal(*, carton_proposal, shipment, created_by):
    if carton_proposal.source == PreparationProposalSource.DEPOSIT:
        converted_carton = _reassign_deposit_carton(
            carton_proposal=carton_proposal,
            shipment=shipment,
            user=created_by,
        )
    elif carton_proposal.source == PreparationProposalSource.ASF_STOCK:
        converted_carton = _pack_carton_from_preparation_reservations(
            carton_proposal=carton_proposal,
            shipment=shipment,
            user=created_by,
        )
    else:
        raise StockError("Source de proposition non supportée.")

    carton_proposal.converted_carton = converted_carton
    carton_proposal.status = PreparationShipmentProposalStatus.CONVERTED
    carton_proposal.save(update_fields=["converted_carton", "status", "updated_at"])
    return converted_carton


@transaction.atomic
def convert_preparation_run(*, run, created_by):
    created_shipments = []
    proposals = (
        run.shipment_proposals.select_related(
            "shipper__organization",
            "recipient_organization__organization",
            "destination",
        )
        .prefetch_related("carton_proposals__reservations")
        .order_by(
            "shipper__organization__name",
            "recipient_organization__organization__name",
            "sequence",
            "id",
        )
    )
    for proposal in proposals:
        if proposal_is_deleted(proposal):
            continue
        if proposal.converted_shipment_id:
            continue
        if proposal.status not in {
            PreparationShipmentProposalStatus.ACCEPTED,
            PreparationShipmentProposalStatus.PARTIAL,
        }:
            continue
        accepted_cartons = [
            carton_proposal
            for carton_proposal in proposal.carton_proposals.order_by("id")
            if carton_proposal.status == PreparationShipmentProposalStatus.ACCEPTED
            and not carton_is_deleted(carton_proposal)
            and carton_proposal.converted_carton_id is None
        ]
        if not accepted_cartons:
            continue

        shipment = _build_shipment_for_proposal(proposal=proposal, created_by=created_by)
        for carton_proposal in accepted_cartons:
            _convert_carton_proposal(
                carton_proposal=carton_proposal,
                shipment=shipment,
                created_by=created_by,
            )
        proposal.converted_shipment = shipment
        proposal.status = PreparationShipmentProposalStatus.CONVERTED
        proposal.save(update_fields=["converted_shipment", "status", "updated_at"])
        created_shipments.append(shipment)

    if created_shipments:
        run.status = PreparationRunStatus.CONVERTED
        run.save(update_fields=["status", "updated_at"])
    return created_shipments
