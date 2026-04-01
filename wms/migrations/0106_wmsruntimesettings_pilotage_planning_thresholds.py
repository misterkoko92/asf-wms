from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0105_planningcommunicationartifact"),
    ]

    operations = [
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="pilotage_planning_critical_pct",
            field=models.PositiveIntegerField(default=95),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="pilotage_planning_tension_pct",
            field=models.PositiveIntegerField(default=80),
        ),
    ]
