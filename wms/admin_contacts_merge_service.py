from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from contacts.capabilities import ensure_contact_capability
from contacts.models import Contact, ContactAddress, ContactType

from .models import (
    Destination,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


def _merge_scalar_fields(source: Contact, target: Contact):
    updated_fields = []
    for field_name in ("title", "email", "email2", "phone", "phone2", "role", "notes"):
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
            updated_fields.append(field_name)
    if source.contact_type == ContactType.PERSON and not target.use_organization_address:
        if source.use_organization_address:
            target.use_organization_address = True
            updated_fields.append("use_organization_address")
    if not target.is_active and source.is_active:
        target.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        target.save(update_fields=updated_fields)


def _address_identity(address: ContactAddress):
    return (
        (address.address_line1 or "").strip(),
        (address.address_line2 or "").strip(),
        (address.postal_code or "").strip(),
        (address.city or "").strip(),
        (address.region or "").strip(),
        (address.country or "").strip(),
    )


def _merge_addresses(source: Contact, target: Contact):
    existing_identities = {_address_identity(address) for address in target.addresses.all()}
    for address in source.addresses.all().order_by("id"):
        identity = _address_identity(address)
        if identity in existing_identities:
            continue
        ContactAddress.objects.create(
            contact=target,
            label=address.label,
            address_line1=address.address_line1,
            address_line2=address.address_line2,
            postal_code=address.postal_code,
            city=address.city,
            region=address.region,
            country=address.country,
            phone=address.phone,
            email=address.email,
            is_default=not target.addresses.filter(is_default=True).exists() and address.is_default,
            notes=address.notes,
        )
        existing_identities.add(identity)


def _merge_capabilities(source: Contact, target: Contact):
    for capability in source.capabilities.filter(is_active=True):
        ensure_contact_capability(target, capability.capability)


def _merge_authorized_contacts(
    *,
    source_recipient_contact: ShipmentRecipientContact,
    target_recipient_contact: ShipmentRecipientContact,
):
    for authorization in ShipmentAuthorizedRecipientContact.objects.filter(
        recipient_contact=source_recipient_contact
    ).order_by("id"):
        existing = ShipmentAuthorizedRecipientContact.objects.filter(
            link=authorization.link,
            recipient_contact=target_recipient_contact,
        ).first()
        if existing is None:
            authorization.recipient_contact = target_recipient_contact
            authorization.save(update_fields=["recipient_contact"])
            if authorization.is_default:
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=authorization.link,
                    is_default=True,
                ).exclude(pk=authorization.pk).update(is_default=False)
            continue

        updated_fields = []
        if authorization.is_active and not existing.is_active:
            existing.is_active = True
            updated_fields.append("is_active")
        if authorization.is_default and not existing.is_default:
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=authorization.link,
                is_default=True,
            ).exclude(pk=existing.pk).update(is_default=False)
            existing.is_default = True
            updated_fields.append("is_default")
        if updated_fields:
            existing.save(update_fields=updated_fields)
        authorization.delete()


def _merge_shipper_links(
    *, source_link: ShipmentShipperRecipientLink, target_link: ShipmentShipperRecipientLink
):
    for authorization in ShipmentAuthorizedRecipientContact.objects.filter(
        link=source_link
    ).order_by("id"):
        existing = ShipmentAuthorizedRecipientContact.objects.filter(
            link=target_link,
            recipient_contact=authorization.recipient_contact,
        ).first()
        if existing is None:
            authorization.link = target_link
            authorization.save(update_fields=["link"])
            if authorization.is_default:
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    is_default=True,
                ).exclude(pk=authorization.pk).update(is_default=False)
            continue

        updated_fields = []
        if authorization.is_active and not existing.is_active:
            existing.is_active = True
            updated_fields.append("is_active")
        if authorization.is_default and not existing.is_default:
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=target_link,
                is_default=True,
            ).exclude(pk=existing.pk).update(is_default=False)
            existing.is_default = True
            updated_fields.append("is_default")
        if updated_fields:
            existing.save(update_fields=updated_fields)
        authorization.delete()
    source_link.delete()


def _merge_shippers(source: Contact, target: Contact):
    target_shipper = ShipmentShipper.objects.filter(organization=target).first()
    for shipper in ShipmentShipper.objects.filter(organization=source).order_by("id"):
        if target_shipper is None:
            shipper.organization = target
            shipper.save(update_fields=["organization"])
            target_shipper = shipper
            continue

        updated_fields = []
        if target_shipper.default_contact_id is None and shipper.default_contact_id is not None:
            target_shipper.default_contact = shipper.default_contact
            updated_fields.append("default_contact")
        if (
            shipper.validation_status == ShipmentValidationStatus.VALIDATED
            and target_shipper.validation_status != ShipmentValidationStatus.VALIDATED
        ):
            target_shipper.validation_status = ShipmentValidationStatus.VALIDATED
            updated_fields.append("validation_status")
        if shipper.can_send_to_all and not target_shipper.can_send_to_all:
            target_shipper.can_send_to_all = True
            updated_fields.append("can_send_to_all")
        if shipper.is_active and not target_shipper.is_active:
            target_shipper.is_active = True
            updated_fields.append("is_active")
        if updated_fields:
            target_shipper.save(update_fields=updated_fields)

        for link in ShipmentShipperRecipientLink.objects.filter(shipper=shipper).order_by("id"):
            existing_link = ShipmentShipperRecipientLink.objects.filter(
                shipper=target_shipper,
                recipient_organization=link.recipient_organization,
            ).first()
            if existing_link is None:
                link.shipper = target_shipper
                link.save(update_fields=["shipper"])
                continue
            _merge_shipper_links(source_link=link, target_link=existing_link)
        shipper.delete()


def _merge_recipient_organizations(source: Contact, target: Contact):
    target_recipient_org = ShipmentRecipientOrganization.objects.filter(organization=target).first()
    for recipient_org in ShipmentRecipientOrganization.objects.filter(organization=source).order_by(
        "id"
    ):
        if target_recipient_org is None:
            recipient_org.organization = target
            recipient_org.save(update_fields=["organization"])
            target_recipient_org = recipient_org
            continue

        if target_recipient_org.destination_id != recipient_org.destination_id:
            raise ValidationError(
                "Les structures destinataires fusionnées doivent rester sur la même destination."
            )

        updated_fields = []
        if recipient_org.is_correspondent and not target_recipient_org.is_correspondent:
            target_recipient_org.is_correspondent = True
            updated_fields.append("is_correspondent")
        if recipient_org.is_active and not target_recipient_org.is_active:
            target_recipient_org.is_active = True
            updated_fields.append("is_active")
        if (
            recipient_org.validation_status == ShipmentValidationStatus.VALIDATED
            and target_recipient_org.validation_status != ShipmentValidationStatus.VALIDATED
        ):
            target_recipient_org.validation_status = ShipmentValidationStatus.VALIDATED
            updated_fields.append("validation_status")
        if updated_fields:
            target_recipient_org.save(update_fields=updated_fields)

        for recipient_contact in ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_org
        ).order_by("id"):
            existing_recipient_contact = ShipmentRecipientContact.objects.filter(
                recipient_organization=target_recipient_org,
                contact=recipient_contact.contact,
            ).first()
            if existing_recipient_contact is None:
                recipient_contact.recipient_organization = target_recipient_org
                recipient_contact.save(update_fields=["recipient_organization"])
                continue
            _merge_authorized_contacts(
                source_recipient_contact=recipient_contact,
                target_recipient_contact=existing_recipient_contact,
            )
            recipient_contact.delete()

        for link in ShipmentShipperRecipientLink.objects.filter(
            recipient_organization=recipient_org
        ).order_by("id"):
            existing_link = ShipmentShipperRecipientLink.objects.filter(
                shipper=link.shipper,
                recipient_organization=target_recipient_org,
            ).first()
            if existing_link is None:
                link.recipient_organization = target_recipient_org
                link.save(update_fields=["recipient_organization"])
                continue
            _merge_shipper_links(source_link=link, target_link=existing_link)

        recipient_org.delete()


def _merge_person_references(source: Contact, target: Contact):
    if source.organization_id and not target.organization_id:
        target.organization = source.organization
        target.save(update_fields=["organization"])
    elif (
        source.organization_id
        and target.organization_id
        and source.organization_id != target.organization_id
    ):
        raise ValidationError("Les personnes fusionnées doivent appartenir à la même structure.")

    ShipmentShipper.objects.filter(default_contact=source).update(default_contact=target)
    Destination.objects.filter(correspondent_contact=source).update(correspondent_contact=target)

    for recipient_contact in ShipmentRecipientContact.objects.filter(contact=source).order_by("id"):
        existing = ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_contact.recipient_organization,
            contact=target,
        ).first()
        if existing is None:
            recipient_contact.contact = target
            recipient_contact.save(update_fields=["contact"])
            continue
        _merge_authorized_contacts(
            source_recipient_contact=recipient_contact,
            target_recipient_contact=existing,
        )
        recipient_contact.delete()


def merge_contacts(*, source_contact: Contact, target_contact: Contact):
    if source_contact.pk == target_contact.pk:
        return target_contact
    if source_contact.contact_type != target_contact.contact_type:
        raise ValidationError("Les fiches à fusionner doivent être du même type.")

    with transaction.atomic():
        _merge_scalar_fields(source_contact, target_contact)
        _merge_capabilities(source_contact, target_contact)
        _merge_addresses(source_contact, target_contact)

        if source_contact.contact_type == ContactType.ORGANIZATION:
            source_contact.members.update(organization=target_contact)
            _merge_shippers(source_contact, target_contact)
            _merge_recipient_organizations(source_contact, target_contact)
        else:
            _merge_person_references(source_contact, target_contact)

        if source_contact.is_active:
            source_contact.is_active = False
            source_contact.save(update_fields=["is_active"])
        return target_contact
