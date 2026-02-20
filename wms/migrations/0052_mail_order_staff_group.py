from django.db import migrations


GROUP_NAME = "Mail_Order_Staff"


def create_mail_order_staff_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GROUP_NAME)


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("wms", "0051_wmsruntimesettingsaudit"),
    ]

    operations = [
        migrations.RunPython(
            create_mail_order_staff_group,
            reverse_code=noop_reverse,
        ),
    ]
