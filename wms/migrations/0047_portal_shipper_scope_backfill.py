import unicodedata

from django.db import migrations
from django.db.models import Q


def _normalize(value):
    text = str(value or "")
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(normalized.lower().split())


def backfill_portal_shipper_scope(apps, schema_editor):
    AssociationRecipient = apps.get_model("wms", "AssociationRecipient")
    Contact = apps.get_model("contacts", "Contact")
    ContactTag = apps.get_model("contacts", "ContactTag")

    shipper_aliases = {
        _normalize("expediteur"),
        _normalize("expediteurs"),
        _normalize("expéditeur"),
        _normalize("expéditeurs"),
    }
    recipient_aliases = {
        _normalize("destinataire"),
        _normalize("destinataires"),
        _normalize("beneficiaire"),
        _normalize("beneficiaires"),
        _normalize("bénéficiaire"),
        _normalize("bénéficiaires"),
    }

    shipper_tag = None
    recipient_tag = None
    for tag in ContactTag.objects.only("id", "name"):
        normalized_name = _normalize(tag.name)
        if shipper_tag is None and normalized_name in shipper_aliases:
            shipper_tag = tag
        if recipient_tag is None and normalized_name in recipient_aliases:
            recipient_tag = tag
    if shipper_tag is None and recipient_tag is None:
        return

    association_contact_ids = set()
    recipients = AssociationRecipient.objects.exclude(association_contact__isnull=True)
    for recipient in recipients.iterator():
        association = recipient.association_contact
        association_contact_ids.add(association.id)
        if shipper_tag is not None:
            association.tags.add(shipper_tag.id)
        if recipient.destination_id:
            association.destinations.add(recipient.destination_id)

    for association_id in association_contact_ids:
        association = Contact.objects.filter(pk=association_id).first()
        if association is None:
            continue
        filters = Q(pk=association.id)
        name = (association.name or "").strip()
        email = (association.email or "").strip()
        if name:
            filters |= Q(name__iexact=name)
        if email:
            filters |= Q(email__iexact=email)
        candidate_shipper_ids = set()
        if shipper_tag is not None:
            candidate_shipper_ids = set(
                Contact.objects.filter(is_active=True, tags__id=shipper_tag.id)
                .filter(filters)
                .values_list("id", flat=True)
            )
        candidate_shipper_ids.add(association.id)
        if not candidate_shipper_ids:
            continue

        if recipient_tag is None:
            continue
        source_prefix = f"[Portail association] {association}"
        portal_recipients = (
            Contact.objects.filter(tags__id=recipient_tag.id)
            .filter(
                Q(linked_shippers=association)
                | Q(notes__startswith=source_prefix)
            )
            .distinct()
        )
        for recipient_contact in portal_recipients.iterator():
            recipient_contact.linked_shippers.add(*candidate_shipper_ids)


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0046_sync_associationrecipients_to_contacts"),
    ]

    operations = [
        migrations.RunPython(
            backfill_portal_shipper_scope,
            migrations.RunPython.noop,
        ),
    ]
