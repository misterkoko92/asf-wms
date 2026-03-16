from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0088_preparateur_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="CartonSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("family", models.CharField(max_length=2, unique=True)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["family"],
            },
        ),
        migrations.AddField(
            model_name="carton",
            name="preassigned_destination",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="preassigned_cartons",
                to="wms.destination",
            ),
        ),
        migrations.AddField(
            model_name="cartonitem",
            name="display_expires_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
