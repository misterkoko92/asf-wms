from django.db import migrations, models
import django.db.models.deletion


def backfill_association_recipient_fields(apps, schema_editor):
    AssociationRecipient = apps.get_model("wms", "AssociationRecipient")
    batch = []
    for recipient in AssociationRecipient.objects.all().iterator():
        changed = False
        if not (recipient.structure_name or "").strip() and (recipient.name or "").strip():
            recipient.structure_name = (recipient.name or "").strip()
            changed = True
        if not (recipient.emails or "").strip() and (recipient.email or "").strip():
            recipient.emails = (recipient.email or "").strip()
            changed = True
        if not (recipient.phones or "").strip() and (recipient.phone or "").strip():
            recipient.phones = (recipient.phone or "").strip()
            changed = True
        if changed:
            batch.append(recipient)
    if batch:
        AssociationRecipient.objects.bulk_update(
            batch,
            ["structure_name", "emails", "phones"],
            batch_size=200,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0043_sync_association_portail_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="associationrecipient",
            name="contact_first_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="contact_last_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="contact_title",
            field=models.CharField(
                blank=True,
                choices=[
                    ("mr", "M."),
                    ("mrs", "Mme"),
                    ("ms", "Mlle"),
                    ("dr", "Dr"),
                    ("pr", "Pr"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="destination",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="association_recipients",
                to="wms.destination",
            ),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="emails",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="is_delivery_contact",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="notify_deliveries",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="phones",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="associationrecipient",
            name="structure_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterModelOptions(
            name="associationrecipient",
            options={
                "ordering": [
                    "association_contact__name",
                    "structure_name",
                    "name",
                    "contact_last_name",
                    "contact_first_name",
                ]
            },
        ),
        migrations.RunPython(
            backfill_association_recipient_fields,
            migrations.RunPython.noop,
        ),
    ]
