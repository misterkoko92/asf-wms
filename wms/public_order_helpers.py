from contacts.models import Contact, ContactType

from .models import (
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
)
from .scan_helpers import parse_int


def _clean_text(value):
    return (value or "").strip()


def _resolve_existing_contact(form_data):
    contact_id = parse_int(form_data.get("association_contact_id"))
    if contact_id:
        contact = Contact.objects.filter(id=contact_id, is_active=True).first()
        if contact:
            return contact

    association_name = _clean_text(form_data.get("association_name"))
    if not association_name:
        return None
    return Contact.objects.filter(
        name__iexact=association_name,
        is_active=True,
    ).first()


def _sync_contact_identity(contact, form_data):
    updated_fields = []
    association_name = _clean_text(form_data.get("association_name"))
    association_email = _clean_text(form_data.get("association_email"))
    association_phone = _clean_text(form_data.get("association_phone"))

    if association_name and contact.name != association_name:
        contact.name = association_name
        updated_fields.append("name")
    if association_email and contact.email != association_email:
        contact.email = association_email
        updated_fields.append("email")
    if association_phone and contact.phone != association_phone:
        contact.phone = association_phone
        updated_fields.append("phone")
    if contact.contact_type != ContactType.ORGANIZATION:
        contact.contact_type = ContactType.ORGANIZATION
        updated_fields.append("contact_type")
    if not contact.is_active:
        contact.is_active = True
        updated_fields.append("is_active")
    if updated_fields:
        contact.save(update_fields=updated_fields)


def _ensure_recipient_org_role(contact, form_data):
    assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
        organization=contact,
        role=OrganizationRole.RECIPIENT,
        defaults={"is_active": False},
    )

    association_email = _clean_text(form_data.get("association_email"))
    association_phone = _clean_text(form_data.get("association_phone"))

    org_contact = None
    if association_email:
        org_contact = (
            OrganizationContact.objects.filter(
                organization=contact,
                email__iexact=association_email,
            )
            .order_by("id")
            .first()
        )
    if org_contact is None:
        org_contact = (
            OrganizationContact.objects.filter(organization=contact).order_by("id").first()
        )

    if org_contact is None:
        org_contact = OrganizationContact.objects.create(
            organization=contact,
            last_name=contact.name or "",
            email=association_email,
            phone=association_phone,
            is_active=True,
        )
    else:
        org_contact_updates = []
        if association_email and org_contact.email != association_email:
            org_contact.email = association_email
            org_contact_updates.append("email")
        if association_phone and org_contact.phone != association_phone:
            org_contact.phone = association_phone
            org_contact_updates.append("phone")
        if not org_contact.is_active:
            org_contact.is_active = True
            org_contact_updates.append("is_active")
        if org_contact_updates:
            org_contact.save(update_fields=org_contact_updates)

    role_contact, _ = OrganizationRoleContact.objects.get_or_create(
        role_assignment=assignment,
        contact=org_contact,
        defaults={"is_primary": True, "is_active": True},
    )
    if not role_contact.is_active or not role_contact.is_primary:
        role_contact.is_active = True
        role_contact.is_primary = True
        role_contact.save(update_fields=["is_active", "is_primary"])
    OrganizationRoleContact.objects.filter(
        role_assignment=assignment,
        is_primary=True,
    ).exclude(pk=role_contact.pk).update(is_primary=False)

    if not assignment.is_active and _clean_text(org_contact.email):
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])


def upsert_public_order_contact(form_data):
    contact = _resolve_existing_contact(form_data)
    if not contact:
        contact = Contact.objects.create(
            name=_clean_text(form_data.get("association_name")),
            contact_type=ContactType.ORGANIZATION,
            email=_clean_text(form_data.get("association_email")),
            phone=_clean_text(form_data.get("association_phone")),
            is_active=True,
        )

    _sync_contact_identity(contact, form_data)
    _ensure_recipient_org_role(contact, form_data)
    return contact
