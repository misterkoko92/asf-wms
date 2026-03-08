from django import forms
from django.utils.translation import gettext_lazy as _

from .models import PlanningRun


class PlanningRunForm(forms.ModelForm):
    class Meta:
        model = PlanningRun
        fields = [
            "week_start",
            "week_end",
            "parameter_set",
            "flight_mode",
            "flight_batch",
        ]
        labels = {
            "week_start": _("Debut de semaine"),
            "week_end": _("Fin de semaine"),
            "parameter_set": _("Jeu de parametres"),
            "flight_mode": _("Mode vols"),
            "flight_batch": _("Batch vols existant"),
        }
        widgets = {
            "week_start": forms.DateInput(attrs={"type": "date"}),
            "week_end": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        week_start = cleaned_data.get("week_start")
        week_end = cleaned_data.get("week_end")
        if week_start and week_end and week_end < week_start:
            self.add_error("week_end", _("La fin de semaine doit etre apres le debut."))
        return cleaned_data
