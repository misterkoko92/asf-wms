from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0092_associationrecipient_synced_contact"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="wmsruntimesettings",
            name="design_custom_presets",
        ),
        migrations.RemoveField(
            model_name="wmsruntimesettings",
            name="design_selected_preset",
        ),
        migrations.RemoveField(
            model_name="wmsruntimesettings",
            name="scan_bootstrap_enabled",
        ),
        migrations.DeleteModel(
            name="UserUiPreference",
        ),
    ]
