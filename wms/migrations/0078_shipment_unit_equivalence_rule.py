from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0077_receipt_pickup_billing_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShipmentUnitEquivalenceRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("label", models.CharField(max_length=120)),
                ("applies_to_hors_format", models.BooleanField(default=False)),
                ("units_per_item", models.PositiveIntegerField(default=1)),
                ("priority", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shipment_unit_equivalence_rules",
                        to="wms.productcategory",
                    ),
                ),
            ],
            options={
                "ordering": ["priority", "id"],
            },
        ),
    ]
