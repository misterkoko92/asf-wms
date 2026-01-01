from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0026_associationprofile_must_change_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="review_status",
            field=models.CharField(
                choices=[
                    ("pending_validation", "En attente validation"),
                    ("approved", "Valider"),
                    ("rejected", "Refuser"),
                    ("changes_requested", "Modifier"),
                ],
                default="pending_validation",
                max_length=30,
            ),
        ),
    ]
