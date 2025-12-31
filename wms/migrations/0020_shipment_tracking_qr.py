from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0019_carton_dimensions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="shipment",
            name="qr_code_image",
            field=models.ImageField(blank=True, upload_to="qr_codes/shipments/"),
        ),
        migrations.CreateModel(
            name="ShipmentTrackingEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("planning_ok", "OK pour planification"), ("planned", "Planifie"), ("moved_export", "Deplace au magasin export"), ("boarding_ok", "OK mise a bord"), ("received_correspondent", "Recu correspondant"), ("received_recipient", "Recu destinataire")], max_length=40)),
                ("actor_name", models.CharField(max_length=120)),
                ("actor_structure", models.CharField(max_length=120)),
                ("comments", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("shipment", models.ForeignKey(on_delete=models.CASCADE, related_name="tracking_events", to="wms.shipment")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

