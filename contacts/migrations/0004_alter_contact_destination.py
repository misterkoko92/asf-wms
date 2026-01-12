from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0003_contact_destination"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="destination",
            field=models.ForeignKey(
                blank=True,
                help_text="Laisser vide pour toutes les destinations.",
                limit_choices_to={"is_active": True},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="contacts",
                to="wms.destination",
            ),
        ),
    ]
