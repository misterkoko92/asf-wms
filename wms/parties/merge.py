from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from contacts.capabilities import ensure_contact_capability
from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    Destination,
    RecipientStructureDocument,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.parties.invariants import recipient_organizations_share_destination


@dataclass(frozen=True)
class RecipientOrganizationMergeResult:
    source_recipient_organization_id: int
    target_recipient_organization_id: int
    migrated_recipient_contact_count: int
    migrated_shipper_link_count: int


def _merge_scalar_fields(source: Contact, target: Contact):
    updated_fields = []
    for field_name in ("title", "email", "email2", "phone", "phone2", "role", "notes"):
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
            updated_fields.append(field_name)
    if source.contact_type == ContactType.ORGANIZATION:
        if not target.legal_form and source.legal_form:
            target.legal_form = source.legal_form
            updated_fields.append("legal_form")
        if target.beneficiary_count is None and source.beneficiary_count is not None:
            target.beneficiary_count = source.beneficiary_count
            updated_fields.append("beneficiary_count")
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


def _merge_recipient_structure_documents(source: Contact, target: Contact):
    for document in RecipientStructureDocument.objects.filter(contact=source).order_by("id"):
        existing = RecipientStructureDocument.objects.filter(
            contact=target,
            doc_type=document.doc_type,
        ).first()
        if existing is None:
            document.contact = target
            document.save(update_fields=["contact"])
            continue
        document.delete()


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


def _merge_recipient_organizations_for_contacts(source: Contact, target: Contact):
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
            _merge_recipient_structure_documents(source_contact, target_contact)
            _merge_shippers(source_contact, target_contact)
            _merge_recipient_organizations_for_contacts(source_contact, target_contact)
        else:
            _merge_person_references(source_contact, target_contact)

        if source_contact.is_active:
            source_contact.is_active = False
            source_contact.save(update_fields=["is_active"])
        return target_contact


def merge_recipient_organizations(
    *, source: ShipmentRecipientOrganization, target: ShipmentRecipientOrganization
) -> RecipientOrganizationMergeResult:
    if source is None or target is None:
        raise ValidationError("Structure destinataire introuvable.")
    if source.pk == target.pk:
        raise ValidationError("La source et la cible doivent etre distinctes.")
    if not recipient_organizations_share_destination(source, target):
        raise ValidationError("La fusion doit rester sur la meme escale.")

    duplicate_contact_ids_to_delete = []
    duplicate_link_ids_to_delete = []
    migrated_contact_count = 0
    migrated_link_count = 0

    with transaction.atomic():
        contact_map = {}
        source_recipient_contacts = list(
            ShipmentRecipientContact.objects.select_related("contact")
            .filter(recipient_organization=source)
            .order_by("id")
        )
        for source_recipient_contact in source_recipient_contacts:
            person = source_recipient_contact.contact
            if person.organization_id != target.organization_id:
                person.organization = target.organization
                person.save(update_fields=["organization"])

            target_recipient_contact = (
                ShipmentRecipientContact.objects.filter(
                    recipient_organization=target,
                    contact=person,
                )
                .exclude(pk=source_recipient_contact.pk)
                .first()
            )
            if target_recipient_contact is None:
                source_recipient_contact.recipient_organization = target
                source_recipient_contact.save(update_fields=["recipient_organization"])
                target_recipient_contact = source_recipient_contact
            else:
                if source_recipient_contact.is_active and not target_recipient_contact.is_active:
                    target_recipient_contact.is_active = True
                    target_recipient_contact.save(update_fields=["is_active"])
                duplicate_contact_ids_to_delete.append(source_recipient_contact.pk)
            contact_map[source_recipient_contact.pk] = target_recipient_contact
            migrated_contact_count += 1

        link_map = {}
        target_link_default_exists = {}
        source_links = list(
            ShipmentShipperRecipientLink.objects.filter(recipient_organization=source).order_by(
                "id"
            )
        )
        for source_link in source_links:
            target_link = (
                ShipmentShipperRecipientLink.objects.filter(
                    shipper=source_link.shipper,
                    recipient_organization=target,
                )
                .exclude(pk=source_link.pk)
                .first()
            )
            if target_link is None:
                source_link.recipient_organization = target
                source_link.save(update_fields=["recipient_organization"])
                target_link = source_link
            else:
                if source_link.is_active and not target_link.is_active:
                    target_link.is_active = True
                    target_link.save(update_fields=["is_active"])
                duplicate_link_ids_to_delete.append(source_link.pk)
            link_map[source_link.pk] = target_link
            target_link_default_exists[target_link.pk] = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    is_default=True,
                    is_active=True,
                ).exists()
            )
            migrated_link_count += 1

        source_authorizations = list(
            ShipmentAuthorizedRecipientContact.objects.select_related("recipient_contact")
            .filter(link_id__in=link_map.keys())
            .order_by("id")
        )
        for authorization in source_authorizations:
            target_link = link_map[authorization.link_id]
            target_recipient_contact = contact_map[authorization.recipient_contact_id]
            desired_default = (
                authorization.is_default
                and authorization.is_active
                and not target_link_default_exists.get(target_link.pk, False)
            )

            target_authorization = (
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    recipient_contact=target_recipient_contact,
                )
                .exclude(pk=authorization.pk)
                .first()
            )
            if target_authorization is None:
                update_fields = []
                if authorization.link_id != target_link.pk:
                    authorization.link = target_link
                    update_fields.append("link")
                if authorization.recipient_contact_id != target_recipient_contact.pk:
                    authorization.recipient_contact = target_recipient_contact
                    update_fields.append("recipient_contact")
                if authorization.is_default != desired_default:
                    authorization.is_default = desired_default
                    update_fields.append("is_default")
                if update_fields:
                    authorization.save(update_fields=update_fields)
                if desired_default:
                    target_link_default_exists[target_link.pk] = True
                continue

            updated_fields = []
            if authorization.is_active and not target_authorization.is_active:
                target_authorization.is_active = True
                updated_fields.append("is_active")
            if desired_default and not target_authorization.is_default:
                ShipmentAuthorizedRecipientContact.objects.filter(
                    link=target_link,
                    is_default=True,
                ).exclude(pk=target_authorization.pk).update(is_default=False)
                target_authorization.is_default = True
                updated_fields.append("is_default")
                target_link_default_exists[target_link.pk] = True
            if updated_fields:
                target_authorization.save(update_fields=updated_fields)
            authorization.delete()

        if duplicate_link_ids_to_delete:
            ShipmentShipperRecipientLink.objects.filter(
                id__in=duplicate_link_ids_to_delete
            ).delete()
        if duplicate_contact_ids_to_delete:
            ShipmentRecipientContact.objects.filter(id__in=duplicate_contact_ids_to_delete).delete()

        if source.is_correspondent and not target.is_correspondent:
            ShipmentRecipientOrganization.objects.filter(
                destination=target.destination,
                is_correspondent=True,
            ).exclude(pk=target.pk).update(is_correspondent=False)
            target.is_correspondent = True
            target.save(update_fields=["is_correspondent"])

        source.is_active = False
        source.is_correspondent = False
        source.save(update_fields=["is_active", "is_correspondent"])
        source.organization.is_active = False
        source.organization.save(update_fields=["is_active"])

    return RecipientOrganizationMergeResult(
        source_recipient_organization_id=source.id,
        target_recipient_organization_id=target.id,
        migrated_recipient_contact_count=migrated_contact_count,
        migrated_shipper_link_count=migrated_link_count,
    )
