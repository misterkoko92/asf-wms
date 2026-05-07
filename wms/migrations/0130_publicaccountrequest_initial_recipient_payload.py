from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0129_order_inbound_delivery_pallet_guidelines"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicaccountrequest",
            name="initial_recipient_payload",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
