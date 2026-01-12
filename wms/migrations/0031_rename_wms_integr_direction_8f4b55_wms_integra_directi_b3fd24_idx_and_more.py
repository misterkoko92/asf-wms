from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0030_integration_event"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="integrationevent",
            new_name="wms_integra_directi_b3fd24_idx",
            old_name="wms_integr_direction_8f4b55",
        ),
        migrations.RenameIndex(
            model_name="integrationevent",
            new_name="wms_integra_source_0fb495_idx",
            old_name="wms_integr_source_7b7c77",
        ),
    ]
