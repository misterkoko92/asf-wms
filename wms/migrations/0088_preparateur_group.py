from django.db import migrations


GROUP_NAME = "Preparateur"


def create_preparateur_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GROUP_NAME)


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0087_communicationdraft_family"),
    ]

    operations = [
        migrations.RunPython(create_preparateur_group, migrations.RunPython.noop),
    ]
