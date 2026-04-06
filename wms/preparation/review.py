from __future__ import annotations

from copy import deepcopy

from django.db import transaction

from wms.models import (
    PreparationCartonProposal,
    PreparationDecisionAction,
    PreparationDecisionLog,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
)
from wms.preparation.reservations import release_carton_proposal_reservations


def proposal_is_deleted(proposal) -> bool:
    return bool((getattr(proposal, "rationale", None) or {}).get("deleted"))


def carton_is_deleted(carton_proposal) -> bool:
    return bool((getattr(carton_proposal, "rationale", None) or {}).get("deleted"))


def _mark_deleted(instance):
    rationale = deepcopy(instance.rationale or {})
    rationale["deleted"] = True
    instance.rationale = rationale
    instance.save(update_fields=["rationale", "updated_at"])


def _update_shipment_status(shipment_proposal):
    cartons = list(shipment_proposal.carton_proposals.order_by("id"))
    visible_cartons = [carton for carton in cartons if not carton_is_deleted(carton)]
    if not visible_cartons:
        shipment_proposal.status = PreparationShipmentProposalStatus.REJECTED
        _mark_deleted(shipment_proposal)
        shipment_proposal.save(update_fields=["status", "updated_at"])
        return shipment_proposal

    statuses = {carton.status for carton in visible_cartons}
    if statuses == {PreparationShipmentProposalStatus.ACCEPTED}:
        new_status = PreparationShipmentProposalStatus.ACCEPTED
    elif statuses == {PreparationShipmentProposalStatus.REJECTED}:
        new_status = PreparationShipmentProposalStatus.REJECTED
    elif PreparationShipmentProposalStatus.NEEDS_RECALC in statuses:
        new_status = PreparationShipmentProposalStatus.NEEDS_RECALC
    elif (
        PreparationShipmentProposalStatus.ACCEPTED in statuses
        or PreparationShipmentProposalStatus.REJECTED in statuses
    ):
        new_status = PreparationShipmentProposalStatus.PARTIAL
    else:
        new_status = PreparationShipmentProposalStatus.PROPOSED
    shipment_proposal.status = new_status
    shipment_proposal.save(update_fields=["status", "updated_at"])
    return shipment_proposal


def _log_decision(*, run, shipment_proposal, carton_proposal, action, created_by):
    PreparationDecisionLog.objects.create(
        run=run,
        shipment_proposal=shipment_proposal,
        carton_proposal=carton_proposal,
        action=action,
        created_by=created_by,
    )


@transaction.atomic
def apply_preparation_review_action(
    *,
    run,
    action,
    selected_shipment_ids=None,
    selected_carton_ids=None,
    created_by,
):
    selected_shipment_ids = {
        int(value) for value in (selected_shipment_ids or []) if str(value).strip()
    }
    selected_carton_ids = {
        int(value) for value in (selected_carton_ids or []) if str(value).strip()
    }

    shipment_queryset = run.shipment_proposals.all().prefetch_related("carton_proposals")
    carton_queryset = PreparationCartonProposal.objects.filter(shipment_proposal__run=run)

    if action == "accept_all":
        target_cartons = list(carton_queryset.order_by("shipment_proposal_id", "id"))
        action_name = PreparationDecisionAction.ACCEPT
    else:
        shipment_cartons = list(
            carton_queryset.filter(shipment_proposal_id__in=selected_shipment_ids).order_by(
                "shipment_proposal_id",
                "id",
            )
        )
        explicitly_selected = list(
            carton_queryset.filter(id__in=selected_carton_ids).order_by("id")
        )
        target_cartons = shipment_cartons + [
            carton
            for carton in explicitly_selected
            if carton.id not in {row.id for row in shipment_cartons}
        ]
        action_name = {
            "accept_selected": PreparationDecisionAction.ACCEPT,
            "reject_keep_draft": PreparationDecisionAction.REJECT_KEEP_DRAFT,
            "reject_delete": PreparationDecisionAction.REJECT_DELETE,
        }[action]

    touched_shipment_ids = set()
    for carton_proposal in target_cartons:
        shipment_proposal = carton_proposal.shipment_proposal
        touched_shipment_ids.add(shipment_proposal.id)
        if action_name == PreparationDecisionAction.ACCEPT:
            carton_proposal.status = PreparationShipmentProposalStatus.ACCEPTED
            carton_proposal.save(update_fields=["status", "updated_at"])
        else:
            release_carton_proposal_reservations(carton_proposal=carton_proposal)
            carton_proposal.status = PreparationShipmentProposalStatus.REJECTED
            carton_proposal.save(update_fields=["status", "updated_at"])
            if action_name == PreparationDecisionAction.REJECT_DELETE:
                _mark_deleted(carton_proposal)
        _log_decision(
            run=run,
            shipment_proposal=shipment_proposal,
            carton_proposal=carton_proposal,
            action=action_name,
            created_by=created_by,
        )

    for shipment_proposal in shipment_queryset.filter(id__in=touched_shipment_ids):
        if (
            action_name == PreparationDecisionAction.REJECT_DELETE
            and shipment_proposal.id in selected_shipment_ids
        ):
            _mark_deleted(shipment_proposal)
        _update_shipment_status(shipment_proposal)

    if touched_shipment_ids:
        run.status = PreparationRunStatus.FROZEN
        run.save(update_fields=["status", "updated_at"])
    return len(target_cartons)
