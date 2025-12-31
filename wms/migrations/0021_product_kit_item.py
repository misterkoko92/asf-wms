from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0020_shipment_tracking_qr"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductKitItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("quantity", models.PositiveIntegerField(validators=[MinValueValidator(1)])),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="kit_components",
                        to="wms.product",
                    ),
                ),
                (
                    "kit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kit_items",
                        to="wms.product",
                    ),
                ),
            ],
            options={
                "verbose_name": "Product kit item",
                "verbose_name_plural": "Product kit items",
                "ordering": ["kit", "component"],
                "unique_together": {("kit", "component")},
            },
        ),
    ]
