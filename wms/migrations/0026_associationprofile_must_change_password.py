from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0025_portal_association_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="associationprofile",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
    ]
