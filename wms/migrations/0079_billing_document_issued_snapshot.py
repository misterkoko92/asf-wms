from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0078_shipment_unit_equivalence_rule"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingdocument",
            name="issued_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
