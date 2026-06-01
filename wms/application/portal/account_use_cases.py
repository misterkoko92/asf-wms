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
    "phones",
    "emails",
    "address_line1",
    "address_line2",
    "postal_code",
    "city",
    "country",
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


def _normalize_contact_row(row):
    normalized = dict(row)
    normalized["emails"] = (normalized.get("emails") or normalized.get("email") or "").strip()
    normalized["phones"] = (normalized.get("phones") or normalized.get("phone") or "").strip()
    email_values = [item.strip() for item in normalized["emails"].splitlines() if item.strip()]
    phone_values = [item.strip() for item in normalized["phones"].splitlines() if item.strip()]
    normalized["email"] = (
        normalized.get("email") or (email_values[0] if email_values else "")
    ).strip()
    normalized["phone"] = (
        normalized.get("phone") or (phone_values[0] if phone_values else "")
    ).strip()
    normalized["address_line1"] = (normalized.get("address_line1") or "").strip()
    normalized["address_line2"] = (normalized.get("address_line2") or "").strip()
    normalized["postal_code"] = (normalized.get("postal_code") or "").strip()
    normalized["city"] = (normalized.get("city") or "").strip()
    normalized["country"] = (normalized.get("country") or DEFAULT_COUNTRY).strip()
    return normalized


def _upsert_portal_contacts(*, profile, contact_rows):
    existing_contacts = list(profile.portal_contacts.order_by("position", "id"))
    normalized_rows = [_normalize_contact_row(row) for row in contact_rows]

    for index, row in enumerate(normalized_rows):
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
                phones=row["phones"],
                emails=row["emails"],
                address_line1=row["address_line1"],
                address_line2=row["address_line2"],
                postal_code=row["postal_code"],
                city=row["city"],
                country=row["country"],
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

    for contact in existing_contacts[len(normalized_rows) :]:
        if contact.is_active:
            contact.is_active = False
            contact.save(update_fields=["is_active"])


def _contact_row_from_payload(payload, *, is_administrative, is_shipping):
    return {
        "title": (payload.get("title") or "").strip(),
        "last_name": (payload.get("last_name") or "").strip(),
        "first_name": (payload.get("first_name") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "email": (payload.get("email") or "").strip(),
        "phones": (payload.get("phones") or payload.get("phone") or "").strip(),
        "emails": (payload.get("emails") or payload.get("email") or "").strip(),
        "address_line1": (payload.get("address_line1") or "").strip(),
        "address_line2": (payload.get("address_line2") or "").strip(),
        "postal_code": (payload.get("postal_code") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "country": (payload.get("country") or DEFAULT_COUNTRY).strip(),
        "is_administrative": is_administrative,
        "is_shipping": is_shipping,
        "is_billing": False,
    }


def _same_operational_contact(left, right):
    keys = (
        "title",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address_line1",
        "city",
        "country",
    )
    return all((left.get(key) or "").strip() == (right.get(key) or "").strip() for key in keys)


def upsert_operational_contacts_from_payloads(*, profile, contact_payloads):
    contact_payloads = contact_payloads or {}
    admin_payload = contact_payloads.get("admin") or {}
    preparation_payload = contact_payloads.get("preparation") or {}
    contact_rows = []
    if (
        admin_payload
        and preparation_payload
        and _same_operational_contact(admin_payload, preparation_payload)
    ):
        contact_rows.append(
            _contact_row_from_payload(
                admin_payload,
                is_administrative=True,
                is_shipping=True,
            )
        )
    else:
        if admin_payload:
            contact_rows.append(
                _contact_row_from_payload(
                    admin_payload,
                    is_administrative=True,
                    is_shipping=False,
                )
            )
        if preparation_payload:
            contact_rows.append(
                _contact_row_from_payload(
                    preparation_payload,
                    is_administrative=False,
                    is_shipping=True,
                )
            )
    if not contact_rows:
        return
    _upsert_portal_contacts(profile=profile, contact_rows=contact_rows)
    _sync_notification_emails_from_contact_rows(profile, contact_rows)
    profile.save(update_fields=["notification_emails"])


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

        normalized_rows = [_normalize_contact_row(row) for row in contact_rows]
        _upsert_portal_contacts(profile=profile, contact_rows=normalized_rows)
        _sync_notification_emails_from_contact_rows(profile, normalized_rows)
        profile.save(update_fields=["notification_emails"])

    return profile
