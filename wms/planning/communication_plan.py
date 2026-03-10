from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from wms.models import CommunicationChannel, CommunicationTemplate, PlanningVersion

CHANGE_STATUS_PRIORITY = {
    "new": 0,
    "changed": 1,
    "cancelled": 2,
    "unchanged": 3,
}


@dataclass(frozen=True)
class CommunicationAssignmentPayload:
    shipment_reference: str
    shipper_name: str
    destination_iata: str
    volunteer_label: str
    flight_number: str
    departure_date: date | None
    departure_time: str
    cartons: int
    notes: str
    source: str
    status: str
    sequence: int

    def signature(self) -> tuple[object, ...]:
        return (
            self.sequence,
            self.shipment_reference,
            self.shipper_name,
            self.destination_iata,
            self.volunteer_label,
            self.flight_number,
            self.departure_date,
            self.departure_time,
            self.cartons,
            self.notes,
            self.source,
            self.status,
        )


@dataclass(frozen=True)
class CommunicationPlanItem:
    recipient_label: str
    channel: str
    change_status: str
    current_assignments: list[CommunicationAssignmentPayload] = field(default_factory=list)
    previous_assignments: list[CommunicationAssignmentPayload] = field(default_factory=list)
    change_summary: str = ""


@dataclass(frozen=True)
class CommunicationPlan:
    version_id: int
    items: list[CommunicationPlanItem]


def _channel_sort_key(channel: str) -> tuple[int, str]:
    order = {
        CommunicationChannel.EMAIL: 0,
        CommunicationChannel.WHATSAPP: 1,
    }
    return (order.get(channel, 99), channel)


def _resolve_active_channels() -> list[str]:
    channels: list[str] = []
    for channel in (
        CommunicationTemplate.objects.filter(is_active=True)
        .order_by("id")
        .values_list(
            "channel",
            flat=True,
        )
    ):
        if channel not in channels:
            channels.append(str(channel))
    if channels:
        return channels
    return [CommunicationChannel.EMAIL]


def _normalize_assignment(assignment) -> CommunicationAssignmentPayload:
    shipment = assignment.shipment_snapshot
    volunteer = assignment.volunteer_snapshot
    flight = assignment.flight_snapshot
    flight_payload = flight.payload or {} if flight else {}
    return CommunicationAssignmentPayload(
        shipment_reference=shipment.shipment_reference if shipment else "",
        shipper_name=shipment.shipper_name if shipment else "",
        destination_iata=(
            shipment.destination_iata
            if shipment and shipment.destination_iata
            else (flight.destination_iata if flight else "")
        ),
        volunteer_label=volunteer.volunteer_label if volunteer else "",
        flight_number=flight.flight_number if flight else "",
        departure_date=flight.departure_date if flight else None,
        departure_time=str(flight_payload.get("departure_time") or ""),
        cartons=assignment.assigned_carton_count,
        notes=assignment.notes,
        source=assignment.source,
        status=assignment.status,
        sequence=assignment.sequence,
    )


def _group_assignments_by_recipient(
    version: PlanningVersion,
) -> dict[str, list[CommunicationAssignmentPayload]]:
    grouped: dict[str, list[CommunicationAssignmentPayload]] = defaultdict(list)
    assignments = version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by("sequence", "id")
    for assignment in assignments:
        payload = _normalize_assignment(assignment)
        recipient = payload.volunteer_label.strip()
        if not recipient:
            continue
        grouped[recipient].append(payload)

    return {
        recipient: sorted(payloads, key=lambda item: item.signature())
        for recipient, payloads in grouped.items()
    }


def _determine_change_status(
    current_assignments: list[CommunicationAssignmentPayload],
    previous_assignments: list[CommunicationAssignmentPayload],
) -> str:
    if current_assignments and not previous_assignments:
        return "new"
    if previous_assignments and not current_assignments:
        return "cancelled"
    if [item.signature() for item in current_assignments] == [
        item.signature() for item in previous_assignments
    ]:
        return "unchanged"
    return "changed"


def _build_change_summary(
    change_status: str,
    current_assignments: list[CommunicationAssignmentPayload],
    previous_assignments: list[CommunicationAssignmentPayload],
) -> str:
    if change_status == "new":
        return f"{len(current_assignments)} affectation(s) nouvelle(s)"
    if change_status == "changed":
        return (
            f"{len(current_assignments)} affectation(s) courante(s), "
            f"{len(previous_assignments)} precedente(s)"
        )
    if change_status == "cancelled":
        return f"{len(previous_assignments)} affectation(s) annulee(s)"
    return "Aucun changement"


def build_version_communication_plan(version: PlanningVersion) -> CommunicationPlan:
    current_by_recipient = _group_assignments_by_recipient(version)
    previous_by_recipient: dict[str, list[CommunicationAssignmentPayload]] = {}
    if version.based_on_id:
        previous_by_recipient = _group_assignments_by_recipient(version.based_on)

    channels = _resolve_active_channels()
    items: list[CommunicationPlanItem] = []
    recipients = sorted(set(current_by_recipient) | set(previous_by_recipient))
    for recipient in recipients:
        current_assignments = current_by_recipient.get(recipient, [])
        previous_assignments = previous_by_recipient.get(recipient, [])
        change_status = _determine_change_status(current_assignments, previous_assignments)
        change_summary = _build_change_summary(
            change_status,
            current_assignments,
            previous_assignments,
        )
        for channel in channels:
            items.append(
                CommunicationPlanItem(
                    recipient_label=recipient,
                    channel=channel,
                    change_status=change_status,
                    current_assignments=current_assignments,
                    previous_assignments=previous_assignments,
                    change_summary=change_summary,
                )
            )

    items.sort(
        key=lambda item: (
            CHANGE_STATUS_PRIORITY.get(item.change_status, 99),
            item.recipient_label.lower(),
            _channel_sort_key(item.channel),
        )
    )
    return CommunicationPlan(version_id=version.pk, items=items)
