from __future__ import annotations

from django.db import connection, transaction

from wms.domain.stock import StockError, fefo_lots
from wms.models import (
    PreparationDecisionAction,
    PreparationDecisionLog,
    PreparationReservation,
    PreparationReservationStatus,
    PreparationShipmentProposalStatus,
)


def compute_run_usable_stock(*, product, manual_reserve_quantity=0):
    lots = list(fefo_lots(product))
    available_total = sum(max(0, lot.quantity_on_hand - lot.quantity_reserved) for lot in lots)
    return max(0, available_total - max(0, manual_reserve_quantity))


@transaction.atomic
def reserve_stock_for_carton_proposal(
    *,
    run,
    shipment_proposal,
    carton_proposal,
    created_by,
    manual_reserve_quantity=0,
):
    existing = list(
        carton_proposal.reservations.filter(status=PreparationReservationStatus.ACTIVE).order_by(
            "product_lot__expires_on",
            "product_lot__received_on",
            "product_lot__id",
        )
    )
    if existing:
        return existing

    product = carton_proposal.product
    if product is None:
        raise StockError("Produit requis pour reserver le stock.")

    needed = int(carton_proposal.quantity or 0)
    if needed <= 0:
        raise StockError("Quantite de proposition invalide.")

    lots = list(fefo_lots(product, for_update=True))
    available_total = sum(max(0, lot.quantity_on_hand - lot.quantity_reserved) for lot in lots)
    usable_total = max(0, available_total - max(0, manual_reserve_quantity))
    if usable_total < needed:
        raise StockError(f"{product.name}: stock insuffisant ({usable_total}).")

    reservations = []
    remaining = needed
    for lot in lots:
        if remaining <= 0:
            break
        available = lot.quantity_on_hand - lot.quantity_reserved
        if available <= 0:
            continue
        take = min(remaining, available)
        lot.quantity_reserved += take
        lot.save(update_fields=["quantity_reserved"])
        reservation = PreparationReservation.objects.create(
            run=run,
            shipment_proposal=shipment_proposal,
            carton_proposal=carton_proposal,
            product_lot=lot,
            quantity=take,
            status=PreparationReservationStatus.ACTIVE,
            created_by=created_by,
        )
        reservations.append(reservation)
        remaining -= take
    return reservations


@transaction.atomic
def release_carton_proposal_reservations(*, carton_proposal):
    reservations_query = carton_proposal.reservations.filter(
        status=PreparationReservationStatus.ACTIVE
    ).select_related("product_lot")
    if connection.features.has_select_for_update:
        reservations_query = reservations_query.select_for_update()
    for reservation in reservations_query:
        lot = reservation.product_lot
        lot.quantity_reserved = max(0, lot.quantity_reserved - reservation.quantity)
        lot.save(update_fields=["quantity_reserved"])
        reservation.status = PreparationReservationStatus.RELEASED
        reservation.save(update_fields=["status"])


@transaction.atomic
def consume_carton_proposal_reservations(*, carton_proposal):
    reservations_query = carton_proposal.reservations.filter(
        status=PreparationReservationStatus.ACTIVE
    ).select_related("product_lot")
    if connection.features.has_select_for_update:
        reservations_query = reservations_query.select_for_update()
    for reservation in reservations_query:
        lot = reservation.product_lot
        lot.quantity_reserved = max(0, lot.quantity_reserved - reservation.quantity)
        lot.quantity_on_hand = max(0, lot.quantity_on_hand - reservation.quantity)
        lot.save(update_fields=["quantity_reserved", "quantity_on_hand"])
        reservation.status = PreparationReservationStatus.CONSUMED
        reservation.save(update_fields=["status"])


@transaction.atomic
def reclaim_carton_proposal_stock_for_urgency(*, carton_proposal, quantity, created_by, note=""):
    if quantity <= 0:
        raise StockError("Quantite invalide.")

    shipment_proposal = carton_proposal.shipment_proposal
    reservations_query = (
        carton_proposal.reservations.filter(status=PreparationReservationStatus.ACTIVE)
        .select_related("product_lot")
        .order_by(
            "product_lot__expires_on",
            "product_lot__received_on",
            "product_lot__id",
        )
    )
    if connection.features.has_select_for_update:
        reservations_query = reservations_query.select_for_update()
    reservations = list(reservations_query)
    remaining = quantity

    for reservation in reservations:
        if remaining <= 0:
            break
        take = min(remaining, reservation.quantity)
        lot = reservation.product_lot
        lot.quantity_reserved = max(0, lot.quantity_reserved - take)
        lot.save(update_fields=["quantity_reserved"])
        reservation.quantity -= take
        update_fields = ["quantity"]
        if reservation.quantity <= 0:
            reservation.status = PreparationReservationStatus.RELEASED
            update_fields.append("status")
        reservation.save(update_fields=update_fields)
        remaining -= take

    if remaining > 0:
        raise StockError("Reservation insuffisante pour reprise urgente.")

    carton_proposal.status = PreparationShipmentProposalStatus.NEEDS_RECALC
    carton_proposal.save(update_fields=["status"])
    shipment_proposal.status = PreparationShipmentProposalStatus.NEEDS_RECALC
    shipment_proposal.save(update_fields=["status"])
    PreparationDecisionLog.objects.create(
        run=shipment_proposal.run,
        shipment_proposal=shipment_proposal,
        carton_proposal=carton_proposal,
        action=PreparationDecisionAction.RECLAIM_FOR_URGENCY,
        note=note,
        created_by=created_by,
    )
