from dataclasses import dataclass

from django.db import transaction
from django.utils.translation import gettext as _

from contacts.models import Contact

from .models import Destination, Shipment, ShipmentStatus
from .scan_shipment_handlers import _validate_shipment_party_selection
from .services import StockError
from .shipment_helpers import build_destination_label
from .shipment_party_snapshot import build_shipment_party_snapshot_payload
from .shipment_status import sync_shipment_ready_state


@dataclass(frozen=True)
class PreparedShipmentBatchResult:
    shipments: list[Shipment]


class ShipmentBatchValidationError(ValueError):
    def __init__(self, row_errors):
        self.row_errors = row_errors
        super().__init__(_("Batch expédition invalide."))


def _coerce_positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _resolve_instance(model, value):
    if value is None or value == "":
        return None
    if isinstance(value, model):
        return value
    try:
        return model.objects.filter(pk=value).first()
    except (TypeError, ValueError):
        return None


def _validate_batch_row(row, *, index):
    errors = {}
    destination = _resolve_instance(Destination, row.get("destination"))
    shipper_contact = _resolve_instance(Contact, row.get("shipper_contact"))
    recipient_contact = _resolve_instance(Contact, row.get("recipient_contact"))
    posted_correspondent = _resolve_instance(Contact, row.get("correspondent_contact"))
    planned_carton_count = _coerce_positive_int(row.get("planned_carton_count"))

    if destination is None:
        errors["destination"] = _("Destination requise.")
    if shipper_contact is None:
        errors["shipper_contact"] = _("Expéditeur requis.")
    if recipient_contact is None:
        errors["recipient_contact"] = _("Destinataire requis.")
    if planned_carton_count is None:
        errors["planned_carton_count"] = _("Nombre de colis prévus requis.")

    correspondent_contact = None
    if not errors:
        try:
            correspondent_contact = _validate_shipment_party_selection(
                shipper_contact=shipper_contact,
                recipient_contact=recipient_contact,
                destination=destination,
            )
        except StockError as exc:
            errors["__all__"] = str(exc)
        else:
            if (
                posted_correspondent is not None
                and posted_correspondent.pk != correspondent_contact.pk
            ):
                errors["correspondent_contact"] = _(
                    "Correspondant non disponible pour cette destination."
                )

    if errors:
        return None, {index: errors}

    return (
        {
            "destination": destination,
            "shipper_contact": shipper_contact,
            "recipient_contact": recipient_contact,
            "correspondent_contact": correspondent_contact,
            "planned_carton_count": planned_carton_count,
        },
        {},
    )


def create_prepared_shipment_batch(*, rows, user):
    normalized_rows = []
    row_errors = {}
    for index, row in enumerate(rows, start=1):
        normalized, errors = _validate_batch_row(row, index=index)
        if errors:
            row_errors.update(errors)
            continue
        normalized_rows.append(normalized)

    if not normalized_rows and not row_errors:
        row_errors[1] = {"__all__": _("Ajouter au moins une expédition.")}

    if row_errors:
        raise ShipmentBatchValidationError(row_errors)

    shipments = []
    with transaction.atomic():
        for row in normalized_rows:
            destination = row["destination"]
            shipper_contact = row["shipper_contact"]
            recipient_contact = row["recipient_contact"]
            correspondent_contact = row["correspondent_contact"]
            destination_label = build_destination_label(destination)
            party_payload = build_shipment_party_snapshot_payload(
                shipper_contact=shipper_contact,
                recipient_contact=recipient_contact,
                correspondent_contact=correspondent_contact,
                shipper_name=shipper_contact.name,
                recipient_name=recipient_contact.name,
                correspondent_name=correspondent_contact.name,
            )
            shipment = Shipment.objects.create(
                status=ShipmentStatus.DRAFT,
                shipper_name=shipper_contact.name,
                shipper_contact_ref=shipper_contact,
                recipient_name=recipient_contact.name,
                recipient_contact_ref=recipient_contact,
                correspondent_name=correspondent_contact.name,
                correspondent_contact_ref=correspondent_contact,
                destination=destination,
                destination_address=destination_label,
                destination_country=destination.country,
                planned_carton_count=row["planned_carton_count"],
                created_by=user,
                **party_payload,
            )
            sync_shipment_ready_state(shipment)
            shipments.append(shipment)

    return PreparedShipmentBatchResult(shipments=shipments)
