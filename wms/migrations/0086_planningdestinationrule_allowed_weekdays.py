from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0085_flight_route_pos_flight_routing"),
    ]

    operations = [
        migrations.AddField(
            model_name="planningdestinationrule",
            name="allowed_weekdays",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
