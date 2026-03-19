from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0089_carton_sequences_preassignment_manual_expiry"),
    ]

    operations = [
        migrations.DeleteModel(
            name="MigrationReviewItem",
        ),
    ]
