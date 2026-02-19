from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0038_shipment_archived_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CartonStatusEvent",
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
                (
                    "previous_status",
                    models.CharField(
                        choices=[
                            ("draft", "Cree"),
                            ("picking", "En preparation"),
                            ("packed", "Pret"),
                            ("assigned", "Affecte"),
                            ("labeled", "Etiquette"),
                            ("shipped", "Expedie"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "new_status",
                    models.CharField(
                        choices=[
                            ("draft", "Cree"),
                            ("picking", "En preparation"),
                            ("packed", "Pret"),
                            ("assigned", "Affecte"),
                            ("labeled", "Etiquette"),
                            ("shipped", "Expedie"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "carton",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_events",
                        to="wms.carton",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="carton_status_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
