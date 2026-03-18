from django.db import transaction
from django.utils import timezone

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipperScope,
)

PORTAL_RECIPIENT_SOURCE_PREFIX = "[Portail association]"
PORTAL_RECIPIENT_ADDRESS_LABEL = "Portail association"


def _source_marker(recipient_id: int) -> str:
    return f"{PORTAL_RECIPIENT_SOURCE_PREFIX}[recipient_id={recipient_id}]"


def _first_multi_value(raw_value: str, fallback: str = "") -> str:
    value = (raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return (fallback or "").strip()


def _build_contact_notes(recipient) -> str:
    notes = (recipient.notes or "").strip()
    source = _source_marker(recipient.pk)
    association = f"Association: {recipient.association_contact}"
    if notes:
        return f"{source}\n{association}\n{notes}"
    return f"{source}\n{association}"


def _recipient_display_name(recipient) -> str:
    display = (recipient.get_display_name() or "").strip()
    if display:
        return display[:200]
    return f"Destinataire {recipient.pk}"[:200]


def _find_synced_contact_by_marker(recipient):
    if not recipient.pk:
        return None
    return (
        Contact.objects.filter(
            notes__startswith=_source_marker(recipient.pk),
        )
        .order_by("-id")
        .first()
    )


def _upsert_contact_address(*, contact, recipient, primary_phone, primary_email):
    if not recipient.address_line1:
        return
    address = (
        contact.addresses.filter(label=PORTAL_RECIPIENT_ADDRESS_LABEL).order_by("-id").first()
        or contact.addresses.filter(is_default=True).order_by("-id").first()
    )
    if address is None:
        address = ContactAddress(contact=contact)
    address.label = PORTAL_RECIPIENT_ADDRESS_LABEL
    address.address_line1 = recipient.address_line1
    address.address_line2 = recipient.address_line2
    address.postal_code = recipient.postal_code
    address.city = recipient.city
    address.country = recipient.country or "France"
    address.phone = primary_phone[:40]
    address.email = primary_email[:254]
    address.is_default = True
    address.notes = recipient.notes or ""
    address.save()


def _ensure_association_shipper_scope(*, association_contact, destination):
    if association_contact is None:
        return None
    assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
        organization=association_contact,
        role=OrganizationRole.SHIPPER,
        defaults={"is_active": False},
    )
    if destination is not None:
        ShipperScope.objects.update_or_create(
            role_assignment=assignment,
            destination=destination,
            defaults={
                "all_destinations": False,
                "is_active": True,
                "valid_to": None,
            },
        )
    return assignment


def _ensure_primary_recipient_role_contact(
    *, role_assignment, recipient, primary_email, primary_phone
):
    if not primary_email:
        return None

    primary_link = (
        role_assignment.role_contacts.select_related("contact")
        .filter(is_primary=True)
        .order_by("-id")
        .first()
    )
    org_contact = (
        primary_link.contact
        if primary_link is not None
        else role_assignment.organization.organization_contacts.order_by("id").first()
    )
    if org_contact is None:
        org_contact = OrganizationContact(organization=role_assignment.organization)

    org_contact.title = recipient.contact_title or ""
    org_contact.last_name = recipient.contact_last_name[:120]
    org_contact.first_name = recipient.contact_first_name[:120]
    org_contact.email = primary_email[:254]
    org_contact.phone = primary_phone[:40]
    org_contact.is_active = bool(recipient.is_active)
    org_contact.save()

    if primary_link is None:
        role_contact, _ = OrganizationRoleContact.objects.get_or_create(
            role_assignment=role_assignment,
            contact=org_contact,
            defaults={"is_primary": True, "is_active": True},
        )
    else:
        role_contact = primary_link

    updated_fields = []
    if not role_contact.is_primary:
        role_contact.is_primary = True
        updated_fields.append("is_primary")
    target_active = bool(recipient.is_active)
    if role_contact.is_active != target_active:
        role_contact.is_active = target_active
        updated_fields.append("is_active")
    if updated_fields:
        role_contact.save(update_fields=updated_fields)
    return role_contact


def _ensure_recipient_role_assignment(*, contact, recipient, primary_email, primary_phone):
    assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
        organization=contact,
        role=OrganizationRole.RECIPIENT,
        defaults={"is_active": False},
    )
    _ensure_primary_recipient_role_contact(
        role_assignment=assignment,
        recipient=recipient,
        primary_email=primary_email,
        primary_phone=primary_phone,
    )
    target_active = bool(recipient.is_active and primary_email)
    if assignment.is_active != target_active:
        assignment.is_active = target_active
        assignment.save(update_fields=["is_active"])
    return assignment


def _sync_recipient_binding(*, association_contact, recipient_contact, destination, is_active):
    if association_contact is None or recipient_contact is None:
        return None

    active_bindings = RecipientBinding.objects.filter(
        shipper_org=association_contact,
        recipient_org=recipient_contact,
        is_active=True,
    )
    now = timezone.now()
    if destination is None or not is_active:
        active_bindings.update(is_active=False, valid_to=now)
        return None

    active_bindings.exclude(destination=destination).update(is_active=False, valid_to=now)
    binding = (
        RecipientBinding.objects.filter(
            shipper_org=association_contact,
            recipient_org=recipient_contact,
            destination=destination,
            is_active=True,
        )
        .order_by("-valid_from", "-id")
        .first()
    )
    if binding is not None:
        return binding
    return RecipientBinding.objects.create(
        shipper_org=association_contact,
        recipient_org=recipient_contact,
        destination=destination,
        is_active=True,
    )


def sync_association_recipient_to_contact(recipient):
    if not recipient:
        return None
    primary_email = _first_multi_value(recipient.emails, recipient.email)
    primary_phone = _first_multi_value(recipient.phones, recipient.phone)
    target_is_active = bool(recipient.is_active)

    with transaction.atomic():
        _ensure_association_shipper_scope(
            association_contact=recipient.association_contact,
            destination=recipient.destination,
        )

        contact = _find_synced_contact_by_marker(recipient)
        if contact is None:
            contact = Contact.objects.create(
                contact_type=ContactType.ORGANIZATION,
                name=_recipient_display_name(recipient),
                email=primary_email[:254],
                phone=primary_phone[:40],
                notes=_build_contact_notes(recipient),
                is_active=True,
            )
        else:
            contact.contact_type = ContactType.ORGANIZATION
            contact.name = _recipient_display_name(recipient)
            contact.email = primary_email[:254]
            contact.phone = primary_phone[:40]
            contact.notes = _build_contact_notes(recipient)
            contact.is_active = True
            contact.save(
                update_fields=[
                    "contact_type",
                    "name",
                    "email",
                    "phone",
                    "notes",
                    "is_active",
                ]
            )

        _upsert_contact_address(
            contact=contact,
            recipient=recipient,
            primary_phone=primary_phone,
            primary_email=primary_email,
        )
        _ensure_recipient_role_assignment(
            contact=contact,
            recipient=recipient,
            primary_email=primary_email,
            primary_phone=primary_phone,
        )
        _sync_recipient_binding(
            association_contact=recipient.association_contact,
            recipient_contact=contact,
            destination=recipient.destination,
            is_active=bool(recipient.is_active),
        )
        if contact.is_active != target_is_active:
            contact.is_active = target_is_active
            contact.save(update_fields=["is_active"])
        return contact
