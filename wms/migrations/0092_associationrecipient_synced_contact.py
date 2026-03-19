import django.db.models.deletion
from django.db import migrations, models

PORTAL_RECIPIENT_SOURCE_PREFIX = "[Portail association]"


def _strip_portal_marker(notes: str, marker: str) -> str:
    if not notes.startswith(marker):
        return notes
    remaining = notes[len(marker) :]
    if remaining.startswith("\r\n"):
        return remaining[2:]
    if remaining.startswith("\n"):
        return remaining[1:]
    return remaining


def backfill_synced_contacts(apps, schema_editor):
    AssociationRecipient = apps.get_model("wms", "AssociationRecipient")
    Contact = apps.get_model("contacts", "Contact")

    for recipient in AssociationRecipient.objects.exclude(pk__isnull=True).iterator():
        marker = f"{PORTAL_RECIPIENT_SOURCE_PREFIX}[recipient_id={recipient.pk}]"
        contact = (
            Contact.objects.filter(notes__startswith=marker)
            .order_by("-id")
            .first()
        )
        if contact is None:
            continue
        AssociationRecipient.objects.filter(pk=recipient.pk).update(synced_contact_id=contact.pk)
        cleaned_notes = _strip_portal_marker(contact.notes or "", marker)
        if cleaned_notes != (contact.notes or ""):
            Contact.objects.filter(pk=contact.pk).update(notes=cleaned_notes)


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0008_remove_contact_tags_remove_contact_destination_and_more"),
        ("wms", "0091_remove_wmsruntimesettings_org_roles_engine_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="associationrecipient",
            name="synced_contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="synced_portal_recipients",
                to="contacts.contact",
            ),
        ),
        migrations.RunPython(
            backfill_synced_contacts,
            migrations.RunPython.noop,
        ),
    ]
