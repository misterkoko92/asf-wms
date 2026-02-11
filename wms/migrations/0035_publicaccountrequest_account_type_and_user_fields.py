from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0034_alter_integrationevent_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicaccountrequest",
            name="account_type",
            field=models.CharField(
                choices=[
                    ("association", "Association"),
                    ("user", "Utilisateur WMS"),
                ],
                db_index=True,
                default="association",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="publicaccountrequest",
            name="requested_password_hash",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="publicaccountrequest",
            name="requested_username",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
