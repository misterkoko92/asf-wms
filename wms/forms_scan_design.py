import re

from django import forms

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
    RUNTIME_FIELDS = DESIGN_FIELDS + ("design_font_heading",)
    COLOR_FIELDS = (
        "design_color_primary",
        "design_color_secondary",
        "design_color_background",
        "design_color_surface",
        "design_color_border",
        "design_color_text",
        "design_color_text_soft",
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
            "design_color_primary": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_secondary": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_background": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_surface": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_border": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_text": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
            "design_color_text_soft": forms.TextInput(
                attrs={
                    "type": "color",
                    "class": "scan-design-color-input",
                    "data-color-input": "1",
                }
            ),
        }

    FONT_FIELDS = ("design_font_h1", "design_font_h2", "design_font_h3", "design_font_body")
    RUNTIME_FIELDS = ("scan_bootstrap_enabled",) + RUNTIME_FIELDS

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

    def clean(self):
        cleaned_data = super().clean()
        for field_name in self.COLOR_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La couleur est obligatoire.")
                continue
            if not HEX_COLOR_RE.match(value):
                self.add_error(
                    field_name,
                    "Utilisez le format hexadécimal #RRGGBB.",
                )
            else:
                cleaned_data[field_name] = value.lower()
        for field_name in self.FONT_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La police est obligatoire.")
                continue
            cleaned_data[field_name] = _normalize_font_name(value)
        return cleaned_data
