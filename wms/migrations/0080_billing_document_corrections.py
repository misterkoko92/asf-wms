from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0079_billing_document_issued_snapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="billingdocument",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("issued", "Issued"),
                    ("partially_paid", "Partially paid"),
                    ("paid", "Paid"),
                    ("cancelled", "Cancelled"),
                    ("cancelled_or_corrected", "Cancelled / corrected"),
                ],
                default="draft",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="billingdocument",
            name="correction_state",
            field=models.CharField(
                choices=[
                    ("none", "None"),
                    ("in_review", "In review"),
                    ("resolved", "Resolved"),
                ],
                default="none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="billingdocument",
            name="parent_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="child_documents",
                to="wms.billingdocument",
            ),
        ),
    ]
