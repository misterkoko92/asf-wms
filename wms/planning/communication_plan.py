from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from wms.models import PlanningVersion
from wms.planning.legacy_communications import (
    COMMUNICATION_FAMILY_ORDER,
    CommunicationFamily,
    family_channel,
    family_label,
    family_order_key,
    format_correspondent_contact,
)

CHANGE_STATUS_PRIORITY = {
    "new": 0,
    "changed": 1,
    "cancelled": 2,
    "unchanged": 3,
}


@dataclass(frozen=True)
class CommunicationAssignmentPayload:
    shipment_snapshot_id: int | None
    shipment_reference: str
    shipper_name: str
    shipper_contact: str
    recipient_name: str
    recipient_contact: str
    correspondent_label: str
    correspondent_contact: str
    correspondent_contact_details: str
    destination_city: str
    destination_iata: str
    volunteer_label: str
    volunteer_first_name: str
    volunteer_phone: str
    flight_number: str
    departure_date: date | None
    departure_time: str
    routing: str
    cartons: int
    equivalent_units: int
    shipment_type: str
    notes: str
    source: str
    status: str
    sequence: int

    def signature(self) -> tuple[object, ...]:
        return (
            self.sequence,
            self.shipment_reference,
            self.shipper_name,
            self.recipient_name,
            self.correspondent_label,
            self.destination_city,
            self.destination_iata,
            self.volunteer_label,
            self.flight_number,
            self.departure_date,
            self.departure_time,
            self.routing,
            self.cartons,
            self.equivalent_units,
            self.shipment_type,
            self.notes,
            self.source,
            self.status,
        )


@dataclass(frozen=True)
class CommunicationPlanItem:
    family: str
    family_label: str
    recipient_label: str
    recipient_contact: str
    channel: str
    change_status: str
    current_assignments: list[CommunicationAssignmentPayload] = field(default_factory=list)
    previous_assignments: list[CommunicationAssignmentPayload] = field(default_factory=list)
    change_summary: str = ""


@dataclass(frozen=True)
class CommunicationPlan:
    version_id: int
    items: list[CommunicationPlanItem]


def _first_email(values) -> str:
    for value in values or []:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _normalize_assignment(assignment) -> CommunicationAssignmentPayload:
    shipment = assignment.shipment_snapshot
    volunteer = assignment.volunteer_snapshot
    flight = assignment.flight_snapshot
    shipment_payload = shipment.payload or {} if shipment else {}
    volunteer_payload = volunteer.payload or {} if volunteer else {}
    flight_payload = flight.payload or {} if flight else {}

    shipper_reference = shipment_payload.get("shipper_reference") or {}
    recipient_reference = shipment_payload.get("recipient_reference") or {}
    correspondent_reference = shipment_payload.get("correspondent_reference") or {}
    destination_city = str(shipment_payload.get("destination_city") or "").strip().upper()
    destination_iata = (
        str(shipment.destination_iata or "").strip().upper()
        if shipment is not None
        else str(flight.destination_iata or "").strip().upper()
        if flight is not None
        else ""
    )
    if not destination_city:
        destination_city = destination_iata

    volunteer_label = volunteer.volunteer_label if volunteer else ""
    volunteer_first_name = str(volunteer_payload.get("first_name") or "").strip()
    if not volunteer_first_name and volunteer_label:
        volunteer_first_name = volunteer_label.split()[0]

    return CommunicationAssignmentPayload(
        shipment_snapshot_id=shipment.pk if shipment else None,
        shipment_reference=shipment.shipment_reference if shipment else "",
        shipper_name=str(shipper_reference.get("contact_name") or "").strip()
        or shipment.shipper_name
        if shipment
        else "",
        shipper_contact=_first_email(shipper_reference.get("notification_emails")),
        recipient_name=str(recipient_reference.get("contact_name") or "").strip()
        or str(shipment_payload.get("legacy_destinataire") or "").strip(),
        recipient_contact=_first_email(recipient_reference.get("notification_emails")),
        correspondent_label=str(correspondent_reference.get("contact_name") or "").strip()
        or destination_city,
        correspondent_contact=_first_email(correspondent_reference.get("notification_emails")),
        correspondent_contact_details=format_correspondent_contact(correspondent_reference),
        destination_city=destination_city,
        destination_iata=destination_iata,
        volunteer_label=volunteer_label,
        volunteer_first_name=volunteer_first_name,
        volunteer_phone=str(volunteer_payload.get("phone") or "").strip(),
        flight_number=flight.flight_number if flight else "",
        departure_date=flight.departure_date if flight else None,
        departure_time=str(flight_payload.get("departure_time") or "").strip(),
        routing=str(flight_payload.get("routing") or "").strip(),
        cartons=assignment.assigned_carton_count,
        equivalent_units=shipment.equivalent_units if shipment else 0,
        shipment_type=str(shipment_payload.get("legacy_type") or "").strip(),
        notes=assignment.notes,
        source=assignment.source,
        status=assignment.status,
        sequence=assignment.sequence,
    )


def _group_assignments(version: PlanningVersion) -> list[CommunicationAssignmentPayload]:
    assignments = version.assignments.select_related(
        "shipment_snapshot",
        "volunteer_snapshot",
        "flight_snapshot",
    ).order_by(
        "flight_snapshot__departure_date",
        "flight_snapshot__flight_number",
        "sequence",
        "id",
    )
    return sorted(
        (_normalize_assignment(assignment) for assignment in assignments),
        key=lambda item: item.signature(),
    )


def _families_for_payload(payload: CommunicationAssignmentPayload) -> list[tuple[str, str, str]]:
    return [
        (
            CommunicationFamily.WHATSAPP_BENEVOLE,
            payload.volunteer_label,
            payload.volunteer_phone,
        ),
        (
            CommunicationFamily.EMAIL_ASF,
            "ASF interne",
            "",
        ),
        (
            CommunicationFamily.EMAIL_AIRFRANCE,
            "Air France",
            "",
        ),
        (
            CommunicationFamily.EMAIL_CORRESPONDANT,
            payload.correspondent_label,
            payload.correspondent_contact,
        ),
        (
            CommunicationFamily.EMAIL_EXPEDITEUR,
            payload.shipper_name,
            payload.shipper_contact,
        ),
        (
            CommunicationFamily.EMAIL_DESTINATAIRE,
            payload.recipient_name,
            payload.recipient_contact,
        ),
    ]


def _group_assignments_by_family(
    version: PlanningVersion,
) -> dict[tuple[str, str, str], list[CommunicationAssignmentPayload]]:
    grouped: dict[tuple[str, str, str], list[CommunicationAssignmentPayload]] = defaultdict(list)
    for payload in _group_assignments(version):
        for family, recipient_label, recipient_contact in _families_for_payload(payload):
            if not recipient_label and family not in {
                CommunicationFamily.EMAIL_ASF,
                CommunicationFamily.EMAIL_AIRFRANCE,
            }:
                continue
            grouped[(family, recipient_label, recipient_contact)].append(payload)
    return {key: sorted(items, key=lambda item: item.signature()) for key, items in grouped.items()}


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
            f"{len(previous_assignments)} précédente(s)"
        )
    if change_status == "cancelled":
        return f"{len(previous_assignments)} affectation(s) annulée(s)"
    return "Aucun changement"


def build_version_communication_plan(version: PlanningVersion) -> CommunicationPlan:
    current_by_key = _group_assignments_by_family(version)
    previous_by_key: dict[tuple[str, str, str], list[CommunicationAssignmentPayload]] = {}
    if version.based_on_id:
        previous_by_key = _group_assignments_by_family(version.based_on)

    items: list[CommunicationPlanItem] = []
    keys = sorted(
        set(current_by_key) | set(previous_by_key),
        key=lambda key: (family_order_key(key[0]), key[1].lower(), key[2].lower()),
    )
    for family, recipient_label, recipient_contact in keys:
        current_assignments = current_by_key.get((family, recipient_label, recipient_contact), [])
        previous_assignments = previous_by_key.get((family, recipient_label, recipient_contact), [])
        change_status = _determine_change_status(current_assignments, previous_assignments)
        items.append(
            CommunicationPlanItem(
                family=family,
                family_label=family_label(family),
                recipient_label=recipient_label,
                recipient_contact=recipient_contact,
                channel=family_channel(family),
                change_status=change_status,
                current_assignments=current_assignments,
                previous_assignments=previous_assignments,
                change_summary=_build_change_summary(
                    change_status,
                    current_assignments,
                    previous_assignments,
                ),
            )
        )

    items.sort(
        key=lambda item: (
            family_order_key(item.family),
            CHANGE_STATUS_PRIORITY.get(item.change_status, 99),
            item.recipient_label.lower(),
        )
    )
    return CommunicationPlan(version_id=version.pk, items=items)
