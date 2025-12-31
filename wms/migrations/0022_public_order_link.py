import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0021_product_kit_item"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicOrderLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=200)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
