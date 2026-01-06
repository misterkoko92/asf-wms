from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0002_contact_extensions"),
        ("wms", "0014_destination"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="destination",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"is_active": True},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contacts",
                to="wms.destination",
            ),
        ),
    ]
