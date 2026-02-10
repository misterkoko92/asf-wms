import uuid

from django.db import migrations, models


def _populate_tracking_tokens(apps, schema_editor):
    Shipment = apps.get_model("wms", "Shipment")
    for shipment in Shipment.objects.filter(tracking_token__isnull=True).iterator():
        shipment.tracking_token = uuid.uuid4()
        shipment.save(update_fields=["tracking_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0032_product_pricing_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="tracking_token",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(_populate_tracking_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="shipment",
            name="tracking_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
