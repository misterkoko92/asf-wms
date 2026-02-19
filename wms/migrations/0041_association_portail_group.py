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
)


def create_association_portail_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    AssociationProfile = apps.get_model("wms", "AssociationProfile")

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    permissions = Permission.objects.filter(
        content_type__app_label="wms",
        codename__in=PERMISSION_CODENAMES,
    )
    group.permissions.set(permissions)

    user_ids = list(
        AssociationProfile.objects.values_list("user_id", flat=True).distinct()
    )
    if user_ids:
        group.user_set.add(*user_ids)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("wms", "0040_shipment_closed_fields"),
    ]

    operations = [
        migrations.RunPython(
            create_association_portail_group,
            reverse_code=noop_reverse,
        ),
    ]
