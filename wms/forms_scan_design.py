import re

from django import forms

from .design_tokens import (
    BTN_STYLE_MODE_CHOICES,
    DENSITY_MODE_CHOICES,
    PRIORITY_ONE_TOKEN_COLOR_KEYS,
    PRIORITY_ONE_TOKEN_DEFAULTS,
    PRIORITY_ONE_TOKEN_FIELD_TO_KEY,
    PRIORITY_ONE_TOKEN_INT_KEYS,
    PRIORITY_ONE_TOKEN_SHADOW_KEYS,
    normalize_priority_one_tokens,
)
from .models import WmsRuntimeSettings

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DESIGN_FONT_CHOICES = (
    ("DM Sans", "DM Sans"),
    ("Nunito Sans", "Nunito Sans"),
    ("Manrope", "Manrope"),
    ("Source Sans 3", "Source Sans 3"),
    ("Aptos", "Aptos"),
    ("Segoe UI", "Segoe UI"),
    ("Helvetica Neue", "Helvetica Neue"),
    ("Arial", "Arial"),
)


def _normalize_font_name(value):
    resolved = (value or "").strip()
    if not resolved:
        return ""
    first = resolved.split(",")[0].strip()
    return first.strip('"').strip("'")


def _color_widget_attrs():
    return {
        "type": "color",
        "class": "scan-design-color-input",
        "data-color-input": "1",
    }


class ScanDesignSettingsForm(forms.ModelForm):
    FONT_CHOICES = DESIGN_FONT_CHOICES
    DESIGN_FIELDS = (
        "design_font_h1",
        "design_font_h2",
        "design_font_h3",
        "design_font_body",
        "design_color_primary",
        "design_color_secondary",
        "design_color_background",
        "design_color_surface",
        "design_color_border",
        "design_color_text",
        "design_color_text_soft",
    )
    COLOR_FIELDS = (
        "design_color_primary",
        "design_color_secondary",
        "design_color_background",
        "design_color_surface",
        "design_color_border",
        "design_color_text",
        "design_color_text_soft",
    )
    FONT_FIELDS = ("design_font_h1", "design_font_h2", "design_font_h3", "design_font_body")
    PRIORITY_TOKEN_FIELDS = tuple(PRIORITY_ONE_TOKEN_FIELD_TO_KEY.keys())
    PREVIEW_FIELDS = DESIGN_FIELDS + PRIORITY_TOKEN_FIELDS
    RUNTIME_FIELDS = (
        "scan_bootstrap_enabled",
        "design_font_heading",
        *DESIGN_FIELDS,
        "design_tokens",
    )

    PRIORITY_COLOR_FIELDS = tuple(
        field_name
        for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items()
        if token_key in PRIORITY_ONE_TOKEN_COLOR_KEYS
    )
    PRIORITY_INT_FIELDS = tuple(
        field_name
        for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items()
        if token_key in PRIORITY_ONE_TOKEN_INT_KEYS
    )
    PRIORITY_SHADOW_FIELDS = tuple(
        field_name
        for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items()
        if token_key in PRIORITY_ONE_TOKEN_SHADOW_KEYS
    )

    design_density_mode = forms.ChoiceField(
        choices=DENSITY_MODE_CHOICES,
        label="Densite",
        help_text="Dense / Standard / Aere.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    design_btn_style_mode = forms.ChoiceField(
        choices=BTN_STYLE_MODE_CHOICES,
        label="Style boutons",
        help_text="Flat / Soft / Elevated / Outlined.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    design_btn_radius = forms.IntegerField(
        min_value=0,
        max_value=120,
        label="Rayon bouton (px)",
        help_text="Rayon principal des boutons.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    design_btn_height_md = forms.IntegerField(
        min_value=0,
        max_value=120,
        label="Hauteur bouton md (px)",
        help_text="Hauteur des actions principales.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    design_btn_shadow = forms.CharField(
        max_length=120,
        label="Ombre bouton",
        help_text='Ex: "none" ou "0 1px 2px rgba(0,0,0,.12)".',
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    design_card_radius = forms.IntegerField(
        min_value=0,
        max_value=120,
        label="Rayon card (px)",
        help_text="Rayon des cartes/panneaux.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    design_card_shadow = forms.CharField(
        max_length=120,
        label="Ombre card",
        help_text='Ex: "none" ou "0 2px 8px rgba(...)".',
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    design_input_height = forms.IntegerField(
        min_value=0,
        max_value=120,
        label="Hauteur champ (px)",
        help_text="Hauteur minimale des champs.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    design_input_radius = forms.IntegerField(
        min_value=0,
        max_value=120,
        label="Rayon champ (px)",
        help_text="Rayon des champs de formulaire.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    design_nav_item_active_bg = forms.CharField(
        label="Nav actif - fond",
        help_text="Couleur de fond item actif navbar.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_nav_item_active_text = forms.CharField(
        label="Nav actif - texte",
        help_text="Couleur de texte item actif navbar.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_dropdown_shadow = forms.CharField(
        max_length=120,
        label="Ombre dropdown",
        help_text='Ex: "none" ou "0 4px 12px rgba(...)".',
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    design_table_row_hover_bg = forms.CharField(
        label="Table hover - fond",
        help_text="Couleur de survol des lignes de tableau.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_success_bg = forms.CharField(
        label="Btn success - fond",
        help_text="Etat success des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_success_text = forms.CharField(
        label="Btn success - texte",
        help_text="Etat success des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_success_border = forms.CharField(
        label="Btn success - bordure",
        help_text="Etat success des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_warning_bg = forms.CharField(
        label="Btn warning - fond",
        help_text="Etat warning des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_warning_text = forms.CharField(
        label="Btn warning - texte",
        help_text="Etat warning des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_warning_border = forms.CharField(
        label="Btn warning - bordure",
        help_text="Etat warning des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_danger_bg = forms.CharField(
        label="Btn danger - fond",
        help_text="Etat danger des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_danger_text = forms.CharField(
        label="Btn danger - texte",
        help_text="Etat danger des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )
    design_color_btn_danger_border = forms.CharField(
        label="Btn danger - bordure",
        help_text="Etat danger des boutons.",
        widget=forms.TextInput(attrs=_color_widget_attrs()),
    )

    class Meta:
        model = WmsRuntimeSettings
        fields = [
            "scan_bootstrap_enabled",
            "design_font_h1",
            "design_font_h2",
            "design_font_h3",
            "design_font_body",
            "design_color_primary",
            "design_color_secondary",
            "design_color_background",
            "design_color_surface",
            "design_color_border",
            "design_color_text",
            "design_color_text_soft",
        ]
        labels = {
            "scan_bootstrap_enabled": "Activer Bootstrap global",
            "design_font_h1": "Typo titre H1",
            "design_font_h2": "Typo titre H2",
            "design_font_h3": "Typo titre H3",
            "design_font_body": "Typo texte",
            "design_color_primary": "Couleur primaire",
            "design_color_secondary": "Couleur secondaire",
            "design_color_background": "Couleur fond",
            "design_color_surface": "Couleur surface",
            "design_color_border": "Couleur bordure",
            "design_color_text": "Couleur texte",
            "design_color_text_soft": "Couleur texte secondaire",
        }
        help_texts = {
            "scan_bootstrap_enabled": "Active la couche Bootstrap sur scan/portal/home/login/admin personnalisés.",
            "design_font_h1": "Une seule police (ex: DM Sans).",
            "design_font_h2": "Une seule police (ex: DM Sans).",
            "design_font_h3": "Une seule police (ex: DM Sans).",
            "design_font_body": "Une seule police (ex: Nunito Sans).",
            "design_color_primary": "Applique les boutons/actions principales.",
            "design_color_secondary": "Applique les actions secondaires et accents.",
            "design_color_background": "Fond global des pages.",
            "design_color_surface": "Fond des cartes et panneaux.",
            "design_color_border": "Couleur des bordures.",
            "design_color_text": "Couleur de texte principale.",
            "design_color_text_soft": "Couleur de texte secondaire/aide.",
        }
        widgets = {
            "scan_bootstrap_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "design_font_h1": forms.Select(choices=DESIGN_FONT_CHOICES),
            "design_font_h2": forms.Select(choices=DESIGN_FONT_CHOICES),
            "design_font_h3": forms.Select(choices=DESIGN_FONT_CHOICES),
            "design_font_body": forms.Select(choices=DESIGN_FONT_CHOICES),
            "design_color_primary": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_secondary": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_background": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_surface": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_border": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_text": forms.TextInput(attrs=_color_widget_attrs()),
            "design_color_text_soft": forms.TextInput(attrs=_color_widget_attrs()),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_choices = list(self.FONT_CHOICES)
        base_choice_values = {value for value, _label in base_choices}
        if self.instance and getattr(self.instance, "pk", None):
            for field_name in self.FONT_FIELDS:
                current = getattr(self.instance, field_name, "")
                normalized = _normalize_font_name(current)
                if normalized and normalized not in base_choice_values:
                    extra_choices = base_choices + [(normalized, f"{normalized} (actuelle)")]
                    self.fields[field_name].widget.choices = extra_choices
                else:
                    self.fields[field_name].widget.choices = base_choices
                self.initial[field_name] = normalized
        else:
            for field_name in self.FONT_FIELDS:
                self.fields[field_name].widget.choices = base_choices

        tokens = normalize_priority_one_tokens(
            getattr(self.instance, "design_tokens", PRIORITY_ONE_TOKEN_DEFAULTS)
        )
        for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items():
            self.initial[field_name] = tokens[token_key]

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.COLOR_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La couleur est obligatoire.")
                continue
            if not HEX_COLOR_RE.match(value):
                self.add_error(field_name, "Utilisez le format hexadécimal #RRGGBB.")
                continue
            cleaned_data[field_name] = value.lower()

        for field_name in self.PRIORITY_COLOR_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La couleur est obligatoire.")
                continue
            if not HEX_COLOR_RE.match(value):
                self.add_error(field_name, "Utilisez le format hexadécimal #RRGGBB.")
                continue
            cleaned_data[field_name] = value.lower()

        for field_name in self.FONT_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La police est obligatoire.")
                continue
            cleaned_data[field_name] = _normalize_font_name(value)

        for field_name in self.PRIORITY_SHADOW_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La valeur est obligatoire.")
                continue
            cleaned_data[field_name] = value[:120]

        return cleaned_data

    def save(self, commit=True):
        runtime_settings = super().save(commit=False)
        tokens_payload = {
            token_key: self.cleaned_data.get(field_name)
            for field_name, token_key in PRIORITY_ONE_TOKEN_FIELD_TO_KEY.items()
        }
        runtime_settings.design_tokens = normalize_priority_one_tokens(tokens_payload)
        if commit:
            runtime_settings.save()
        return runtime_settings
