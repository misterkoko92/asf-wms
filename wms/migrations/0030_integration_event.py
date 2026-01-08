from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0029_alter_productcategory_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "direction",
                    models.CharField(
                        choices=[("inbound", "Inbound"), ("outbound", "Outbound")],
                        default="inbound",
                        max_length=20,
                    ),
                ),
                ("source", models.CharField(max_length=80)),
                ("target", models.CharField(blank=True, max_length=80)),
                ("event_type", models.CharField(max_length=120)),
                ("external_id", models.CharField(blank=True, max_length=120)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processed", "Processed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="integrationevent",
            index=models.Index(fields=["direction", "status", "created_at"], name="wms_integr_direction_8f4b55"),
        ),
        migrations.AddIndex(
            model_name="integrationevent",
            index=models.Index(fields=["source", "event_type"], name="wms_integr_source_7b7c77"),
        ),
    ]
