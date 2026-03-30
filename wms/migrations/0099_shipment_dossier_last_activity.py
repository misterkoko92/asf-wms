from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0098_update_contact_label_print_pack_mapping"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="dossier_last_activity_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dossier_last_activity_label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
