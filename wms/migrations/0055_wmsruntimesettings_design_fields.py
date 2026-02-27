from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0054_useruipreference"),
    ]

    operations = [
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_background",
            field=models.CharField(default="#f6f8f5", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_border",
            field=models.CharField(default="#d9e2dc", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_primary",
            field=models.CharField(default="#6f9a8d", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_secondary",
            field=models.CharField(default="#e7c3a8", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_surface",
            field=models.CharField(default="#fffdf9", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_text",
            field=models.CharField(default="#2f3a36", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_color_text_soft",
            field=models.CharField(default="#5a6964", max_length=16),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_font_body",
            field=models.CharField(
                default='"Nunito Sans", "Aptos", "Segoe UI", sans-serif',
                max_length=160,
            ),
        ),
        migrations.AddField(
            model_name="wmsruntimesettings",
            name="design_font_heading",
            field=models.CharField(
                default='"DM Sans", "Aptos", "Segoe UI", sans-serif',
                max_length=160,
            ),
        ),
    ]
