from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0076_billing_domain_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="receipt",
            name="pickup_charge_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=None,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="pickup_charge_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="receipt",
            name="pickup_charge_currency",
            field=models.CharField(blank=True, default="EUR", max_length=3),
        ),
        migrations.AddField(
            model_name="receipt",
            name="pickup_charge_proof",
            field=models.FileField(blank=True, upload_to="receipt_pickup_billing/"),
        ),
    ]
