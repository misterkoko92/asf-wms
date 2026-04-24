from django.db import transaction

from wms.country_choices import DEFAULT_COUNTRY
from wms.models import AssociationPortalContact
from wms.portal_helpers import get_contact_address

PORTAL_CONTACT_FIELD_NAMES = (
    "title",
    "last_name",
    "first_name",
    "phone",
    "email",
    "is_administrative",
    "is_shipping",
    "is_billing",
)


def _sync_notification_emails_from_contact_rows(profile, contact_rows):
    emails = []
    seen = set()
    for row in contact_rows:
        value = (row.get("email") or "").strip()
        if not value:
            continue
        normalized = value.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        emails.append(value)
    profile.notification_emails = ",".join(emails)


def _upsert_portal_contacts(*, profile, contact_rows):
    existing_contacts = list(profile.portal_contacts.order_by("position", "id"))

    for index, row in enumerate(contact_rows):
        contact = existing_contacts[index] if index < len(existing_contacts) else None
        if contact is None:
            AssociationPortalContact.objects.create(
                profile=profile,
                position=index,
                title=row["title"],
                last_name=row["last_name"],
                first_name=row["first_name"],
                phone=row["phone"],
                email=row["email"],
                is_administrative=row["is_administrative"],
                is_shipping=row["is_shipping"],
                is_billing=row["is_billing"],
                is_active=True,
            )
            continue

        update_fields = []
        if contact.position != index:
            contact.position = index
            update_fields.append("position")
        if not contact.is_active:
            contact.is_active = True
            update_fields.append("is_active")
        for field_name in PORTAL_CONTACT_FIELD_NAMES:
            value = row[field_name]
            if getattr(contact, field_name) != value:
                setattr(contact, field_name, value)
                update_fields.append(field_name)
        if update_fields:
            contact.save(update_fields=update_fields)

    for contact in existing_contacts[len(contact_rows) :]:
        if contact.is_active:
            contact.is_active = False
            contact.save(update_fields=["is_active"])


def save_portal_account_profile(*, user, profile, form_data, contact_rows):
    association = profile.contact
    address = get_contact_address(association)

    with transaction.atomic():
        contact_updates = []
        if association.name != form_data["association_name"]:
            association.name = form_data["association_name"]
            contact_updates.append("name")
        if association.email != form_data["association_email"]:
            association.email = form_data["association_email"]
            contact_updates.append("email")
        if association.phone != form_data["association_phone"]:
            association.phone = form_data["association_phone"]
            contact_updates.append("phone")
        if contact_updates:
            association.save(update_fields=contact_updates)

        if not address:
            address = association.addresses.create(
                address_line1=form_data["address_line1"],
                address_line2=form_data["address_line2"],
                postal_code=form_data["postal_code"],
                city=form_data["city"],
                country=form_data["country"] or DEFAULT_COUNTRY,
                phone=form_data["association_phone"],
                email=form_data["association_email"],
                is_default=True,
            )
        else:
            address_updates = []
            if address.address_line1 != form_data["address_line1"]:
                address.address_line1 = form_data["address_line1"]
                address_updates.append("address_line1")
            if address.address_line2 != form_data["address_line2"]:
                address.address_line2 = form_data["address_line2"]
                address_updates.append("address_line2")
            if address.postal_code != form_data["postal_code"]:
                address.postal_code = form_data["postal_code"]
                address_updates.append("postal_code")
            if address.city != form_data["city"]:
                address.city = form_data["city"]
                address_updates.append("city")
            country = form_data["country"] or DEFAULT_COUNTRY
            if address.country != country:
                address.country = country
                address_updates.append("country")
            if address.phone != form_data["association_phone"]:
                address.phone = form_data["association_phone"]
                address_updates.append("phone")
            if address.email != form_data["association_email"]:
                address.email = form_data["association_email"]
                address_updates.append("email")
            if address_updates:
                address.save(update_fields=address_updates)

        if form_data["association_email"] and user.email != form_data["association_email"]:
            user.email = form_data["association_email"]
            user.save(update_fields=["email"])

        _upsert_portal_contacts(profile=profile, contact_rows=contact_rows)
        _sync_notification_emails_from_contact_rows(profile, contact_rows)
        profile.save(update_fields=["notification_emails"])

    return profile
