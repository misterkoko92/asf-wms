from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0064_update_print_pack_cell_mappings_for_latest_templates"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PrintPackDocumentVersion",
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
                ("version", models.PositiveIntegerField()),
                (
                    "xlsx_template_file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="print_pack_template_versions/",
                    ),
                ),
                ("mappings_snapshot", models.JSONField(blank=True, default=list)),
                (
                    "change_type",
                    models.CharField(
                        choices=[("save", "Save"), ("restore", "Restore")],
                        default="save",
                        max_length=20,
                    ),
                ),
                ("change_note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="print_pack_document_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "pack_document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="wms.printpackdocument",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "unique_together": {("pack_document", "version")},
            },
        ),
    ]
