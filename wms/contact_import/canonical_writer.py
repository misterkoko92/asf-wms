from __future__ import annotations

from django.db import transaction

from contacts.capabilities import ContactCapabilityType, ensure_contact_capability
from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)

from .canonical_dataset import BeContactDataset


def _upsert_contact(*, record: dict, contacts_by_key: dict[str, Contact]) -> Contact:
    organization = contacts_by_key.get(record.get("organization_key", ""))
    lookup = {
        "name": record["name"],
        "contact_type": record["contact_type"],
    }
    if record["contact_type"] == ContactType.PERSON:
        lookup["organization"] = organization

    contact = Contact.objects.filter(**lookup).first()
    if contact is None:
        contact = Contact(**lookup)

    updated_fields = []
    for field_name in ("title", "first_name", "last_name", "email"):
        value = record.get(field_name, "")
        if getattr(contact, field_name) != value:
            setattr(contact, field_name, value)
            updated_fields.append(field_name)

    if record["contact_type"] == ContactType.PERSON and contact.organization_id != getattr(
        organization, "id", None
    ):
        contact.organization = organization
        updated_fields.append("organization")

    if not contact.is_active:
        contact.is_active = True
        updated_fields.append("is_active")

    if contact.pk is None:
        contact.save()
    elif updated_fields:
        contact.save(update_fields=updated_fields)

    contacts_by_key[record["key"]] = contact
    return contact


def _apply_capabilities(*, dataset: BeContactDataset, contacts_by_key: dict[str, Contact]) -> None:
    for record in dataset.donors:
        ensure_contact_capability(
            contacts_by_key[record["contact_key"]],
            ContactCapabilityType.DONOR,
        )
    for record in dataset.transporters:
        ensure_contact_capability(
            contacts_by_key[record["contact_key"]],
            ContactCapabilityType.TRANSPORTER,
        )
    for record in dataset.volunteers:
        ensure_contact_capability(
            contacts_by_key[record["contact_key"]],
            ContactCapabilityType.VOLUNTEER,
        )


def apply_be_contact_dataset(dataset: BeContactDataset) -> None:
    with transaction.atomic():
        contacts_by_key: dict[str, Contact] = {}

        for record in sorted(dataset.contacts, key=lambda item: item["contact_type"]):
            _upsert_contact(record=record, contacts_by_key=contacts_by_key)

        _apply_capabilities(dataset=dataset, contacts_by_key=contacts_by_key)

        destinations_by_iata: dict[str, Destination] = {}
        for destination_record in dataset.destinations:
            correspondent_contact = contacts_by_key[destination_record["correspondent_contact_key"]]
            destination, _created = Destination.objects.get_or_create(
                iata_code=destination_record["iata_code"],
                defaults={
                    "city": destination_record["city"],
                    "country": destination_record["country"],
                    "correspondent_contact": correspondent_contact,
                    "is_active": True,
                },
            )
            updated_fields = []
            for field_name in ("city", "country"):
                value = destination_record[field_name]
                if getattr(destination, field_name) != value:
                    setattr(destination, field_name, value)
                    updated_fields.append(field_name)
            if destination.correspondent_contact_id != correspondent_contact.id:
                destination.correspondent_contact = correspondent_contact
                updated_fields.append("correspondent_contact")
            if not destination.is_active:
                destination.is_active = True
                updated_fields.append("is_active")
            if updated_fields:
                destination.save(update_fields=updated_fields)
            destinations_by_iata[destination.iata_code] = destination

        shippers_by_key: dict[str, ShipmentShipper] = {}
        for shipper_record in dataset.shippers:
            organization = contacts_by_key[shipper_record["contact_key"]]
            default_contact = contacts_by_key[shipper_record["default_contact_key"]]
            shipper, _created = ShipmentShipper.objects.update_or_create(
                organization=organization,
                defaults={
                    "default_contact": default_contact,
                    "validation_status": ShipmentValidationStatus.VALIDATED,
                    "can_send_to_all": False,
                    "is_active": True,
                },
            )
            shippers_by_key[shipper_record["key"]] = shipper

        recipient_orgs_by_key: dict[str, ShipmentRecipientOrganization] = {}
        recipient_contacts_by_contact_key: dict[str, ShipmentRecipientContact] = {}
        recipient_orgs_by_contact_key: dict[str, ShipmentRecipientOrganization] = {}
        for recipient_record in dataset.recipients:
            organization = contacts_by_key[recipient_record["contact_key"]]
            destination = destinations_by_iata[recipient_record["destination_iata"]]
            recipient_org, _created = ShipmentRecipientOrganization.objects.update_or_create(
                organization=organization,
                defaults={
                    "destination": destination,
                    "validation_status": ShipmentValidationStatus.VALIDATED,
                    "is_correspondent": bool(recipient_record.get("is_correspondent")),
                    "is_active": True,
                },
            )
            default_contact = contacts_by_key[recipient_record["default_contact_key"]]
            recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
                recipient_organization=recipient_org,
                contact=default_contact,
                defaults={"is_active": True},
            )
            recipient_orgs_by_key[recipient_record["key"]] = recipient_org
            recipient_orgs_by_contact_key[recipient_record["contact_key"]] = recipient_org
            recipient_contacts_by_contact_key[recipient_record["default_contact_key"]] = (
                recipient_contact
            )

        for correspondent_record in dataset.correspondents:
            organization_contact_key = correspondent_record.get("organization_contact_key", "")
            contact_key = correspondent_record.get("contact_key", "")
            if not organization_contact_key or not contact_key:
                continue
            recipient_org = recipient_orgs_by_contact_key.get(organization_contact_key)
            if recipient_org is None:
                continue
            recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
                recipient_organization=recipient_org,
                contact=contacts_by_key[contact_key],
                defaults={"is_active": True},
            )
            recipient_contacts_by_contact_key[contact_key] = recipient_contact

        for link_record in dataset.shipment_links:
            shipper = shippers_by_key[link_record["shipper_key"]]
            recipient_org = recipient_orgs_by_key[link_record["recipient_key"]]
            shipment_link, _created = ShipmentShipperRecipientLink.objects.update_or_create(
                shipper=shipper,
                recipient_organization=recipient_org,
                defaults={"is_active": True},
            )
            default_contact_key = link_record["default_recipient_contact_key"]
            for authorized_contact_key in link_record["authorized_recipient_contact_keys"]:
                recipient_contact = recipient_contacts_by_contact_key[authorized_contact_key]
                authorization, _created = (
                    ShipmentAuthorizedRecipientContact.objects.update_or_create(
                        link=shipment_link,
                        recipient_contact=recipient_contact,
                        defaults={
                            "is_default": authorized_contact_key == default_contact_key,
                            "is_active": True,
                        },
                    )
                )
                updated_fields = []
                expected_is_default = authorized_contact_key == default_contact_key
                if authorization.is_default != expected_is_default:
                    authorization.is_default = expected_is_default
                    updated_fields.append("is_default")
                if not authorization.is_active:
                    authorization.is_active = True
                    updated_fields.append("is_active")
                if updated_fields:
                    authorization.save(update_fields=updated_fields)
