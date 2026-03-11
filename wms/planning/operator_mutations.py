from __future__ import annotations

from django.core.exceptions import ValidationError

from wms.models import PlanningAssignment, PlanningAssignmentSource, PlanningVersionStatus
from wms.planning.operator_options import (
    build_operator_option_context,
    explain_flight_rejection,
    explain_volunteer_rejection,
)


def _ensure_draft(version) -> None:
    if version.status != PlanningVersionStatus.DRAFT:
        raise ValidationError("Seules les versions brouillon sont modifiables.")


def _validate_manual_assignment(
    version,
    *,
    shipment_snapshot,
    volunteer_snapshot,
    flight_snapshot,
    ignore_assignment_id: int | None = None,
) -> None:
    context = build_operator_option_context(version)
    shipment = context["shipments"].get(int(shipment_snapshot.pk))
    volunteer = context["volunteers"].get(int(volunteer_snapshot.pk))
    flight = context["flights"].get(int(flight_snapshot.pk))
    if shipment is None or volunteer is None or flight is None:
        raise ValidationError("Selection planning invalide.")

    flight_reason = explain_flight_rejection(
        context,
        shipment=shipment,
        flight=flight,
        ignore_assignment_id=ignore_assignment_id,
    )
    if flight_reason == "remaining_capacity_insufficient":
        raise ValidationError(
            "Le vol selectionne n'a pas assez de capacite restante pour cette expedition."
        )
    if flight_reason == "flight_capacity_insufficient":
        raise ValidationError(
            "Le vol selectionne n'a pas la capacite requise pour cette expedition."
        )
    if flight_reason == "weekday_not_allowed":
        raise ValidationError(
            "Le vol selectionne n'est pas autorise pour cette destination a cette date."
        )
    if flight_reason == "max_cartons_per_flight":
        raise ValidationError(
            "Le vol selectionne depasse la limite de colis autorisee pour cette destination."
        )
    if flight_reason is not None:
        raise ValidationError("Le vol selectionne n'est pas compatible avec cette expedition.")

    volunteer_reason = explain_volunteer_rejection(
        context,
        volunteer=volunteer,
        flight=flight,
        ignore_assignment_id=ignore_assignment_id,
    )
    if volunteer_reason == "conflict":
        raise ValidationError(
            "Le benevole selectionne est deja affecte sur un creneau incompatible (marge 2h30)."
        )
    if volunteer_reason == "unavailable":
        raise ValidationError("Le benevole selectionne est indisponible pour ce vol.")


def delete_assignment(*, version, assignment) -> None:
    _ensure_draft(version)
    if assignment.version_id != version.pk:
        raise ValidationError("Affectation introuvable pour cette version.")
    assignment.delete()


def update_assignment(*, version, assignment, volunteer_snapshot, flight_snapshot):
    _ensure_draft(version)
    if assignment.version_id != version.pk:
        raise ValidationError("Affectation introuvable pour cette version.")
    _validate_manual_assignment(
        version,
        shipment_snapshot=assignment.shipment_snapshot,
        volunteer_snapshot=volunteer_snapshot,
        flight_snapshot=flight_snapshot,
        ignore_assignment_id=assignment.pk,
    )
    assignment.volunteer_snapshot = volunteer_snapshot
    assignment.flight_snapshot = flight_snapshot
    assignment.source = PlanningAssignmentSource.MANUAL
    assignment.save(
        update_fields=[
            "volunteer_snapshot",
            "flight_snapshot",
            "source",
            "updated_at",
        ]
    )
    return assignment


def assign_unassigned_shipment(*, version, shipment_snapshot, volunteer_snapshot, flight_snapshot):
    _ensure_draft(version)
    _validate_manual_assignment(
        version,
        shipment_snapshot=shipment_snapshot,
        volunteer_snapshot=volunteer_snapshot,
        flight_snapshot=flight_snapshot,
    )
    sequence = (
        version.assignments.order_by("-sequence", "-id").values_list("sequence", flat=True).first()
        or 0
    ) + 1
    return PlanningAssignment.objects.create(
        version=version,
        shipment_snapshot=shipment_snapshot,
        volunteer_snapshot=volunteer_snapshot,
        flight_snapshot=flight_snapshot,
        assigned_carton_count=shipment_snapshot.carton_count,
        source=PlanningAssignmentSource.MANUAL,
        sequence=sequence,
    )
