from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0027_order_review_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="color",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="product",
            name="photo",
            field=models.ImageField(blank=True, upload_to="product_photos/"),
        ),
        migrations.CreateModel(
            name="RackColor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("zone", models.CharField(max_length=40)),
                ("color", models.CharField(max_length=40)),
                (
                    "warehouse",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="wms.warehouse"),
                ),
            ],
            options={
                "ordering": ["warehouse", "zone"],
                "unique_together": {("warehouse", "zone")},
            },
        ),
    ]
