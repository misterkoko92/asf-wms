from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0100_shipment_structured_dispute_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowBlockageClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("blockage_key", models.CharField(max_length=160, unique=True)),
                ("category", models.CharField(max_length=32)),
                ("label", models.CharField(blank=True, max_length=120)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("owner", models.CharField(blank=True, max_length=20)),
                ("claimed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "claimed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="workflow_blockage_claims",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-claimed_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="workflowblockageclaim",
            index=models.Index(fields=["category", "claimed_at"], name="wms_workflo_categor_25334f_idx"),
        ),
    ]
