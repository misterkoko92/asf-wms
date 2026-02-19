from django.db import migrations


GROUP_NAME = "Association_Portail"
PERMISSION_CODENAMES = (
    "view_product",
    "view_order",
    "add_order",
    "view_associationrecipient",
    "add_associationrecipient",
    "change_associationrecipient",
    "view_accountdocument",
    "add_accountdocument",
    "view_orderdocument",
    "add_orderdocument",
    "view_associationportalcontact",
    "add_associationportalcontact",
    "change_associationportalcontact",
)


def sync_group_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    permissions = Permission.objects.filter(
        content_type__app_label="wms",
        codename__in=PERMISSION_CODENAMES,
    )
    group.permissions.set(permissions)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0042_associationportalcontact"),
    ]

    operations = [
        migrations.RunPython(sync_group_permissions, reverse_code=noop_reverse),
    ]
