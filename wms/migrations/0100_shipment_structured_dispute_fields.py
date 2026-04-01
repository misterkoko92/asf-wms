from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0099_shipment_dossier_last_activity"),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="dispute_due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_opened_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_owner",
            field=models.CharField(
                blank=True,
                choices=[
                    ("magasin", "Magasin"),
                    ("qualite", "Qualité"),
                    ("admin", "Admin"),
                    ("transport", "Transport"),
                    ("portal", "Portail"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("docs_missing", "Documents manquants"),
                    ("data_mismatch", "Écart de données"),
                    ("damage_loss", "Casse / perte"),
                    ("transport_blocked", "Blocage transport"),
                    ("delivery_issue", "Incident livraison"),
                    ("other", "Autre"),
                ],
                default="",
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_resolution_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="shipment",
            name="dispute_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("open", "Ouvert"),
                    ("in_progress", "En cours"),
                    ("waiting_external", "En attente externe"),
                    ("resolved", "Résolu"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]
