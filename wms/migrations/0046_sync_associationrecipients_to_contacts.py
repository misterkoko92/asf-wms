import unicodedata

from django.db import migrations


def _normalize(value):
    text = str(value or "")
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(normalized.lower().split())


def _first_multi_value(raw_value, fallback=""):
    value = str(raw_value or "").replace("\n", ";").replace(",", ";")
    for item in value.split(";"):
        normalized = item.strip()
        if normalized:
            return normalized
    return str(fallback or "").strip()


def _display_name(recipient):
    structure = (recipient.structure_name or "").strip()
    if structure:
        return structure[:200]
    legacy_name = (recipient.name or "").strip()
    if legacy_name:
        return legacy_name[:200]
    title_map = {
        "mr": "M.",
        "mrs": "Mme",
        "ms": "Mlle",
        "dr": "Dr",
        "pr": "Pr",
    }
    last_name = (recipient.contact_last_name or "").strip().upper()
    parts = [
        title_map.get((recipient.contact_title or "").strip(), ""),
        (recipient.contact_first_name or "").strip(),
        last_name,
    ]
    display = " ".join(part for part in parts if part).strip()
    if display:
        return display[:200]
    return f"Destinataire {recipient.pk}"[:200]


def sync_association_recipients_to_contacts(apps, schema_editor):
    AssociationRecipient = apps.get_model("wms", "AssociationRecipient")
    Contact = apps.get_model("contacts", "Contact")
    ContactAddress = apps.get_model("contacts", "ContactAddress")
    ContactTag = apps.get_model("contacts", "ContactTag")

    recipient_aliases = {
        _normalize("destinataire"),
        _normalize("destinataires"),
        _normalize("beneficiaire"),
        _normalize("beneficiaires"),
        _normalize("bénéficiaire"),
        _normalize("bénéficiaires"),
    }
    recipient_tag = None
    for tag in ContactTag.objects.only("id", "name"):
        if _normalize(tag.name) in recipient_aliases:
            recipient_tag = tag
            break
    if recipient_tag is None:
        recipient_tag = ContactTag.objects.create(name="Destinataire")

    default_shipper = (
        Contact.objects.filter(
            is_active=True,
            name__iexact="AVIATION SANS FRONTIERES",
        )
        .order_by("id")
        .first()
    )

    for recipient in AssociationRecipient.objects.all().iterator():
        primary_email = _first_multi_value(recipient.emails, recipient.email)[:254]
        primary_phone = _first_multi_value(recipient.phones, recipient.phone)[:40]
        notes = (recipient.notes or "").strip()
        source = f"[Portail association] {recipient.association_contact}"
        full_notes = f"{source}\n{notes}".strip() if notes else source

        contact = Contact.objects.create(
            contact_type="organization",
            name=_display_name(recipient),
            email=primary_email,
            phone=primary_phone,
            destination_id=recipient.destination_id,
            notes=full_notes,
            is_active=recipient.is_active,
        )

        if recipient.address_line1:
            ContactAddress.objects.create(
                contact_id=contact.id,
                label="Portail association",
                address_line1=recipient.address_line1,
                address_line2=recipient.address_line2,
                postal_code=recipient.postal_code,
                city=recipient.city,
                country=recipient.country or "France",
                phone=primary_phone,
                email=primary_email,
                is_default=True,
                notes=recipient.notes or "",
            )

        contact.tags.add(recipient_tag.id)
        if recipient.destination_id:
            contact.destinations.add(recipient.destination_id)
        if recipient.association_contact_id:
            contact.linked_shippers.add(recipient.association_contact_id)
        if default_shipper and default_shipper.id != contact.id:
            contact.linked_shippers.add(default_shipper.id)


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0045_alter_carton_status_and_more"),
    ]

    operations = [
        migrations.RunPython(
            sync_association_recipients_to_contacts,
            migrations.RunPython.noop,
        ),
    ]
