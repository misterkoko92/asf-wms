from django.db import migrations


GROUP_NAMES = (
    "Account_User_Validation",
    "Shipment_Status_Update",
    "Shipment_Status_Update_Correspondant",
)


def create_notification_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for group_name in GROUP_NAMES:
        Group.objects.get_or_create(name=group_name)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("wms", "0052_mail_order_staff_group"),
    ]

    operations = [
        migrations.RunPython(
            create_notification_groups,
            reverse_code=noop_reverse,
        ),
    ]
