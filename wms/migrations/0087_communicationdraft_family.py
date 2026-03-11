from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0086_planningdestinationrule_allowed_weekdays"),
    ]

    operations = [
        migrations.AddField(
            model_name="communicationdraft",
            name="family",
            field=models.CharField(
                blank=True,
                choices=[
                    ("whatsapp_benevole", "WhatsApp bénévoles"),
                    ("email_asf", "Mail ASF interne"),
                    ("email_airfrance", "Mail Air France"),
                    ("email_correspondant", "Mail Correspondants"),
                    ("email_expediteur", "Mail Expéditeurs"),
                    ("email_destinataire", "Mail Destinataires"),
                ],
                max_length=40,
            ),
        ),
        migrations.AlterModelOptions(
            name="communicationdraft",
            options={
                "ordering": ["version_id", "family", "channel", "recipient_label", "id"],
            },
        ),
    ]
