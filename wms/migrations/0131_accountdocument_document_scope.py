from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0130_publicaccountrequest_initial_recipient_payload"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountdocument",
            name="document_scope",
            field=models.CharField(
                choices=[
                    ("account", "Compte expéditeur"),
                    ("initial_recipient", "Premier destinataire"),
                ],
                default="account",
                max_length=40,
            ),
        ),
    ]
