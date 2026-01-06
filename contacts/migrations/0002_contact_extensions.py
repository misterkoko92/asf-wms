from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contacts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contacttag",
            name="asf_prefix",
            field=models.CharField(
                blank=True, max_length=10, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="contacttag",
            name="asf_last_number",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="contact",
            name="title",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="contact",
            name="first_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="contact",
            name="last_name",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="contact",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"contact_type": "organization"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="members",
                to="contacts.contact",
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="role",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="contact",
            name="email2",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="contact",
            name="phone2",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="contact",
            name="siret",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="contact",
            name="vat_number",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="contact",
            name="legal_registration_number",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="contact",
            name="asf_id",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="use_organization_address",
            field=models.BooleanField(default=False),
        ),
    ]
