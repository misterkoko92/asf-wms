from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import (
    Destination,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationShipperMode,
    PreparationShipperRule,
    ShipmentShipper,
)

ALLOWED_WEEKDAY_TOKENS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_CHOICES = (
    ("mon", "Lun"),
    ("tue", "Mar"),
    ("wed", "Mer"),
    ("thu", "Jeu"),
    ("fri", "Ven"),
    ("sat", "Sam"),
    ("sun", "Dim"),
)
WEEKDAY_LABELS = dict(WEEKDAY_CHOICES)
DEFAULT_TARGET_EQUIVALENT_UNITS = 200
DEFAULT_TARGET_SHIPMENT_COUNT = 15
DEFAULT_TARGET_SHIPMENT_SIZE_UNITS = 10
DEFAULT_MIN_SHIPMENT_SIZE_UNITS = 8
DEFAULT_MAX_SHIPMENT_SIZE_UNITS = 22


def _weekday_summary(values):
    normalized = [value for value in values if value in WEEKDAY_LABELS]
    if not normalized or len(normalized) == len(WEEKDAY_CHOICES):
        return "Tous les jours"
    return ", ".join(WEEKDAY_LABELS[value] for value in normalized)


def _append_widget_class(field, css_class):
    existing_class = field.widget.attrs.get("class", "").strip()
    classes = [value for value in existing_class.split() if value]
    if css_class not in classes:
        classes.append(css_class)
    field.widget.attrs["class"] = " ".join(classes)


def _last_used_parameter_set_id_for_user(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    last_used_for_user = (
        PreparationRun.objects.filter(created_by=user)
        .order_by("-created_at", "-id")
        .values_list("parameter_set_id", flat=True)
        .first()
    )
    if last_used_for_user:
        return last_used_for_user
    return (
        PreparationRun.objects.order_by("-created_at", "-id")
        .values_list("parameter_set_id", flat=True)
        .first()
    )


def _default_parameter_set_id(user):
    last_used = _last_used_parameter_set_id_for_user(user)
    if last_used:
        return last_used
    current = (
        PreparationParameterSet.objects.filter(is_current=True)
        .order_by("-updated_at", "-id")
        .values_list("id", flat=True)
        .first()
    )
    if current:
        return current
    return (
        PreparationParameterSet.objects.order_by("name", "id").values_list("id", flat=True).first()
    )


def _default_flight_window(today=None):
    reference_date = today or timezone.localdate()
    start_of_week = reference_date - timedelta(days=reference_date.weekday())
    weeks_ahead = 1 if reference_date.weekday() <= 2 else 2
    window_start = start_of_week + timedelta(weeks=weeks_ahead)
    window_end = window_start + timedelta(days=6)
    return window_start, window_end


class ScanPreparationRunForm(forms.Form):
    parameter_set = forms.ModelChoiceField(
        queryset=PreparationParameterSet.objects.none(),
        label="Jeu de paramètres magasin à appliquer",
    )
    shippers = forms.ModelMultipleChoiceField(
        queryset=ShipmentShipper.objects.none(),
        label="Expéditeurs à inclure dans le run",
    )
    destinations = forms.ModelMultipleChoiceField(
        queryset=Destination.objects.none(),
        label="Escales à desservir pendant la période",
    )
    target_equivalent_units = forms.IntegerField(
        min_value=1,
        label="Total colis équivalents cible à préparer sur la période",
        initial=DEFAULT_TARGET_EQUIVALENT_UNITS,
    )
    target_shipment_count = forms.IntegerField(
        min_value=1,
        label="Total expéditions cible à proposer sur la période",
        initial=DEFAULT_TARGET_SHIPMENT_COUNT,
    )
    target_shipment_size_units = forms.IntegerField(
        min_value=1,
        label="Taille cible par expédition (en colis équivalents)",
        initial=DEFAULT_TARGET_SHIPMENT_SIZE_UNITS,
    )
    min_shipment_size_units = forms.IntegerField(
        min_value=1,
        label="Taille minimale par expédition (en colis équivalents)",
        initial=DEFAULT_MIN_SHIPMENT_SIZE_UNITS,
    )
    max_shipment_size_units = forms.IntegerField(
        min_value=1,
        required=False,
        label="Taille maximale par expédition (en colis équivalents)",
        initial=DEFAULT_MAX_SHIPMENT_SIZE_UNITS,
    )
    flight_window_start = forms.DateField(
        label="Début de la fenêtre de vols à interroger",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    flight_window_end = forms.DateField(
        label="Fin de la fenêtre de vols à interroger",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parameter_set"].queryset = PreparationParameterSet.objects.order_by(
            "-is_current",
            "name",
            "id",
        )
        self.fields["shippers"].queryset = (
            ShipmentShipper.objects.filter(
                is_active=True,
                organization__is_active=True,
            )
            .select_related("organization", "default_contact")
            .order_by("organization__name", "id")
        )
        self.fields["destinations"].queryset = Destination.objects.filter(is_active=True).order_by(
            "city",
            "iata_code",
            "id",
        )

        if not self.is_bound:
            default_window_start, default_window_end = _default_flight_window()
            self.initial.setdefault("target_equivalent_units", DEFAULT_TARGET_EQUIVALENT_UNITS)
            self.initial.setdefault("target_shipment_count", DEFAULT_TARGET_SHIPMENT_COUNT)
            self.initial.setdefault(
                "target_shipment_size_units", DEFAULT_TARGET_SHIPMENT_SIZE_UNITS
            )
            self.initial.setdefault("min_shipment_size_units", DEFAULT_MIN_SHIPMENT_SIZE_UNITS)
            self.initial.setdefault("max_shipment_size_units", DEFAULT_MAX_SHIPMENT_SIZE_UNITS)
            self.initial.setdefault("flight_window_start", default_window_start)
            self.initial.setdefault("flight_window_end", default_window_end)
            default_parameter_set = _default_parameter_set_id(user)
            if default_parameter_set and "parameter_set" not in self.initial:
                self.initial["parameter_set"] = default_parameter_set
            if "shippers" not in self.initial:
                self.initial["shippers"] = list(
                    self.fields["shippers"].queryset.values_list("id", flat=True)
                )
            if "destinations" not in self.initial:
                self.initial["destinations"] = list(
                    self.fields["destinations"].queryset.values_list("id", flat=True)
                )

        for field in self.fields.values():
            if isinstance(field, forms.ModelMultipleChoiceField):
                _append_widget_class(field, "form-select")
                _append_widget_class(field, "ui-select--xl")
                field.widget.attrs.setdefault("size", 8)
                continue
            if isinstance(field, forms.ModelChoiceField):
                _append_widget_class(field, "form-select")
                _append_widget_class(field, "ui-select--lg")
                continue
            _append_widget_class(field, "form-control")

    def clean(self):
        cleaned_data = super().clean()
        flight_window_start = cleaned_data.get("flight_window_start")
        flight_window_end = cleaned_data.get("flight_window_end")
        max_shipment_size_units = cleaned_data.get("max_shipment_size_units")
        target_shipment_size_units = cleaned_data.get("target_shipment_size_units")
        min_shipment_size_units = cleaned_data.get("min_shipment_size_units")

        if (
            flight_window_start is not None
            and flight_window_end is not None
            and flight_window_end < flight_window_start
        ):
            self.add_error("flight_window_end", "La fin de fenêtre doit être après le début.")
        if (
            max_shipment_size_units is not None
            and target_shipment_size_units is not None
            and max_shipment_size_units < target_shipment_size_units
        ):
            self.add_error(
                "max_shipment_size_units",
                "La taille maximale doit être supérieure ou égale à la taille cible.",
            )
        if (
            min_shipment_size_units is not None
            and target_shipment_size_units is not None
            and min_shipment_size_units > target_shipment_size_units
        ):
            self.add_error(
                "min_shipment_size_units",
                "La taille minimale doit être inférieure ou égale à la taille cible.",
            )
        return cleaned_data


class PreparationParameterSetForm(forms.ModelForm):
    class Meta:
        model = PreparationParameterSet
        fields = ["name", "notes", "is_current"]
        labels = {
            "name": "Nom du jeu de paramètres",
            "notes": "Notes opérateur",
            "is_current": "Jeu de paramètres actif par défaut",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _append_widget_class(self.fields["name"], "form-control")
        _append_widget_class(self.fields["notes"], "form-control")
        _append_widget_class(self.fields["is_current"], "form-check-input")


class PreparationDestinationRuleForm(forms.ModelForm):
    allowed_weekdays_selection = forms.MultipleChoiceField(
        required=False,
        choices=WEEKDAY_CHOICES,
        label="Jours de vol autorisés",
        help_text="Ne rien sélectionner pour utiliser tous les jours disponibles.",
        widget=forms.SelectMultiple(attrs={"size": 7}),
    )

    class Meta:
        model = PreparationDestinationRule
        fields = [
            "max_equivalent_units_per_flight",
            "max_usable_flights_per_week",
            "max_equivalent_units_per_week",
            "max_shipments_per_week",
            "fairness_weight",
            "is_active",
            "notes",
        ]
        labels = {
            "max_equivalent_units_per_flight": "Capacité max par vol",
            "max_usable_flights_per_week": "Nombre de vols utilisables par semaine",
            "max_equivalent_units_per_week": "Capacité max par semaine",
            "max_shipments_per_week": "Nombre max d'expéditions par semaine",
            "fairness_weight": "Poids d'équité",
            "is_active": "Règle active",
            "notes": "Notes",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial_weekdays = list(self.instance.allowed_weekdays or [])
        self.fields["allowed_weekdays_selection"].initial = initial_weekdays
        selected_for_summary = (
            [
                str(value).lower()
                for value in self.data.getlist(self.add_prefix("allowed_weekdays_selection"))
            ]
            if self.is_bound
            else initial_weekdays
        )
        self.weekday_summary = _weekday_summary(selected_for_summary)
        _append_widget_class(self.fields["allowed_weekdays_selection"], "form-select")
        _append_widget_class(self.fields["allowed_weekdays_selection"], "ui-select--md")
        self.fields["max_equivalent_units_per_flight"].widget.attrs["title"] = (
            "Nombre maximal de colis équivalents préparables sur un vol pour cette escale."
        )
        self.fields["max_equivalent_units_per_week"].widget.attrs["title"] = (
            "Nombre maximal de colis équivalents préparables sur la semaine pour cette escale."
        )
        self.fields["max_shipments_per_week"].widget.attrs["title"] = (
            "Nombre maximal de dossiers d'expédition proposés sur la semaine pour cette escale."
        )
        self.fields["fairness_weight"].widget.attrs["title"] = (
            "Le poids d'équité augmente ou réduit la priorité relative de cette escale dans "
            "le scoring. Exemple: 1,20 favorise l'escale par rapport à 1,00 ; 0,80 la défavorise."
        )
        for field_name, field in self.fields.items():
            if field_name == "is_active":
                _append_widget_class(field, "form-check-input")
            elif field_name == "allowed_weekdays_selection":
                continue
            else:
                _append_widget_class(field, "form-control")

    def clean_allowed_weekdays_selection(self):
        values = [
            str(value).lower()
            for value in (self.cleaned_data.get("allowed_weekdays_selection") or [])
        ]
        invalid_tokens = [token for token in values if token not in ALLOWED_WEEKDAY_TOKENS]
        if invalid_tokens:
            raise forms.ValidationError("Choisir uniquement des jours de vol valides.")
        return values

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.allowed_weekdays = self.cleaned_data.get("allowed_weekdays_selection", [])
        if commit:
            instance.save()
        return instance


class PreparationShipperRuleForm(forms.ModelForm):
    class Meta:
        model = PreparationShipperRule
        fields = ["mode", "score_coefficient", "is_active", "notes"]
        labels = {
            "mode": "Mode de préparation",
            "score_coefficient": "Coefficient de score",
            "is_active": "Règle active",
            "notes": "Notes",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mode"].choices = PreparationShipperMode.choices
        _append_widget_class(self.fields["mode"], "form-select")
        _append_widget_class(self.fields["score_coefficient"], "form-control")
        _append_widget_class(self.fields["is_active"], "form-check-input")
        _append_widget_class(self.fields["notes"], "form-control")


PreparationDestinationRuleFormSet = forms.modelformset_factory(
    PreparationDestinationRule,
    form=PreparationDestinationRuleForm,
    extra=0,
)


PreparationShipperRuleFormSet = forms.modelformset_factory(
    PreparationShipperRule,
    form=PreparationShipperRuleForm,
    extra=0,
)


def build_preparation_destination_rule_formset(parameter_set, *, data=None):
    return PreparationDestinationRuleFormSet(
        data=data,
        queryset=parameter_set.destination_rules.select_related("destination").order_by(
            "destination__city",
            "destination__iata_code",
            "id",
        ),
        prefix="destination_rules",
    )


def build_preparation_shipper_rule_formset(parameter_set, *, data=None):
    return PreparationShipperRuleFormSet(
        data=data,
        queryset=parameter_set.shipper_rules.select_related("shipper__organization").order_by(
            "shipper__organization__name",
            "id",
        ),
        prefix="shipper_rules",
    )
