from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from contacts.models import Contact

from .country_choices import build_country_choices

DUPLICATE_ACTION_CHOICES = (
    ("", _("Choisir...")),
    ("replace", _("Remplacer")),
    ("merge", _("Fusionner")),
    ("duplicate", _("Dupliquer")),
)


class DestinationCrudForm(forms.Form):
    city = forms.CharField(max_length=120, label=_("Ville"))
    iata_code = forms.CharField(max_length=10, label=_("Code IATA"))
    country = forms.ChoiceField(choices=(), label=_("Pays"))
    correspondent_contact_id = forms.ModelChoiceField(
        queryset=Contact.objects.none(),
        required=False,
        label=_("Correspondant par défaut"),
    )
    is_active = forms.BooleanField(required=False, initial=True, label=_("Active"))
    duplicate_candidates_count = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.HiddenInput,
    )
    duplicate_action = forms.ChoiceField(
        required=False,
        choices=DUPLICATE_ACTION_CHOICES,
        label=_("Décision doublon"),
    )
    duplicate_target_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].choices = build_country_choices(
            self._current_country_value(),
            include_blank=True,
        )
        self.fields["correspondent_contact_id"].queryset = Contact.objects.filter(
            is_active=True
        ).order_by("name", "id")
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.HiddenInput):
                continue
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select ui-select--md")
            else:
                widget.attrs.setdefault("class", "form-control")
        self.fields["correspondent_contact_id"].widget.attrs["class"] = "form-select ui-select--lg"
        self.fields["duplicate_action"].widget.attrs["class"] = "form-select ui-select--md"

    def _current_country_value(self):
        if self.is_bound:
            return (self.data.get(self.add_prefix("country")) or "").strip()
        return str(self.initial.get("country") or "").strip()

    def clean_city(self):
        return (self.cleaned_data.get("city") or "").strip()

    def clean_iata_code(self):
        return (self.cleaned_data.get("iata_code") or "").strip().upper()

    def clean_country(self):
        return (self.cleaned_data.get("country") or "").strip()

    def clean(self):
        cleaned_data = super().clean()
        duplicate_candidates_count = cleaned_data.get("duplicate_candidates_count") or 0
        duplicate_action = (cleaned_data.get("duplicate_action") or "").strip()
        duplicate_target_id = cleaned_data.get("duplicate_target_id")

        if duplicate_candidates_count > 0 and not duplicate_action:
            self.add_error(
                "duplicate_action",
                _("Choisissez comment traiter le doublon proposé."),
            )
        if duplicate_action in {"replace", "merge"} and not duplicate_target_id:
            self.add_error(
                "duplicate_target_id",
                _("Choisissez une fiche cible pour la résolution du doublon."),
            )
        return cleaned_data
