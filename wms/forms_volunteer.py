from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import VolunteerConstraint, VolunteerProfile


class VolunteerAccountForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("email", "first_name", "last_name")
        labels = {
            "email": _("Mail"),
            "first_name": _("Prenom"),
            "last_name": _("Nom"),
        }
        widgets = {"email": forms.EmailInput(attrs={"type": "email"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True


class VolunteerProfileForm(forms.ModelForm):
    class Meta:
        model = VolunteerProfile
        fields = (
            "phone",
            "address_line1",
            "postal_code",
            "city",
            "country",
            "geo_latitude",
            "geo_longitude",
        )
        labels = {
            "phone": _("Telephone"),
            "address_line1": _("Rue"),
            "postal_code": _("Code postal"),
            "city": _("Ville"),
            "country": _("Pays"),
        }
        widgets = {
            "geo_latitude": forms.HiddenInput(),
            "geo_longitude": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = False
        self.fields["address_line1"].required = True
        self.fields["postal_code"].required = True
        self.fields["city"].required = True
        self.fields["country"].required = True


class VolunteerConstraintForm(forms.ModelForm):
    class Meta:
        model = VolunteerConstraint
        fields = (
            "max_days_per_week",
            "max_expeditions_per_week",
            "max_expeditions_per_day",
            "max_wait_hours",
        )
        labels = {
            "max_days_per_week": _("Nombre de jours max / semaine"),
            "max_expeditions_per_week": _("Nombre d'expeditions max / semaine"),
            "max_expeditions_per_day": _("Nombre d'expeditions max / jour"),
            "max_wait_hours": _("Attente max (heures)"),
        }
