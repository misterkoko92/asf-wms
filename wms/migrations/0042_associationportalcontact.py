from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0041_association_portail_group"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssociationPortalContact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveSmallIntegerField(default=0)),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("mr", "M."),
                            ("mrs", "Mme"),
                            ("ms", "Mlle"),
                            ("dr", "Dr"),
                            ("pr", "Pr"),
                        ],
                        max_length=10,
                    ),
                ),
                ("last_name", models.CharField(blank=True, max_length=120)),
                ("first_name", models.CharField(blank=True, max_length=120)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("is_administrative", models.BooleanField(default=False)),
                ("is_shipping", models.BooleanField(default=False)),
                ("is_billing", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="portal_contacts",
                        to="wms.associationprofile",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="associationportalcontact",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(is_administrative=True)
                    | models.Q(is_shipping=True)
                    | models.Q(is_billing=True)
                ),
                name="wms_assoc_portal_contact_has_type",
            ),
        ),
    ]
