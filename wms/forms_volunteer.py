from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import VolunteerAvailability, VolunteerConstraint, VolunteerProfile

TIME_INPUT_WIDGET = forms.TimeInput(attrs={"type": "time", "step": "900"})


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


class VolunteerAvailabilityForm(forms.ModelForm):
    class Meta:
        model = VolunteerAvailability
        fields = ("date", "start_time", "end_time")
        labels = {
            "date": _("Date"),
            "start_time": _("Heure debut"),
            "end_time": _("Heure fin"),
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": TIME_INPUT_WIDGET,
            "end_time": TIME_INPUT_WIDGET,
        }

    def __init__(self, *args, volunteer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.volunteer = volunteer
        if volunteer is not None:
            self.instance.volunteer = volunteer
        self.fields["start_time"].input_formats = ["%H:%M", "%H:%M:%S"]
        self.fields["end_time"].input_formats = ["%H:%M", "%H:%M:%S"]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if not start or not end:
            return cleaned
        if start >= end:
            raise forms.ValidationError(_("L'heure de fin doit etre apres l'heure de debut."))
        return cleaned


class VolunteerAvailabilityWeekForm(forms.Form):
    availability = forms.ChoiceField(
        choices=(
            ("unavailable", _("Indisponible")),
            ("available", _("Disponible")),
        ),
        widget=forms.RadioSelect,
        initial="unavailable",
    )
    date = forms.DateField(widget=forms.HiddenInput)
    start_time = forms.TimeField(required=False, widget=TIME_INPUT_WIDGET)
    end_time = forms.TimeField(required=False, widget=TIME_INPUT_WIDGET)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.day_label = ""
        self.fields["start_time"].input_formats = ["%H:%M", "%H:%M:%S"]
        self.fields["end_time"].input_formats = ["%H:%M", "%H:%M:%S"]

    def clean(self):
        cleaned = super().clean()
        availability = cleaned.get("availability")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if availability != "available":
            cleaned["start_time"] = None
            cleaned["end_time"] = None
            return cleaned
        if not start:
            self.add_error("start_time", _("Champ obligatoire."))
        if not end:
            self.add_error("end_time", _("Champ obligatoire."))
        if self.errors:
            return cleaned
        if start >= end:
            self.add_error("end_time", _("L'heure de fin doit etre apres l'heure de debut."))
        return cleaned
