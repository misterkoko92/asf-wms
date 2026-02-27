import re

from django import forms

from .models import WmsRuntimeSettings

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ScanDesignSettingsForm(forms.ModelForm):
    DESIGN_FIELDS = (
        "design_font_heading",
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

    class Meta:
        model = WmsRuntimeSettings
        fields = [
            "design_font_heading",
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
            "design_font_heading": "Typo principale (titres)",
            "design_font_body": "Typo secondaire (texte)",
            "design_color_primary": "Couleur primaire",
            "design_color_secondary": "Couleur secondaire",
            "design_color_background": "Couleur fond",
            "design_color_surface": "Couleur surface",
            "design_color_border": "Couleur bordure",
            "design_color_text": "Couleur texte",
            "design_color_text_soft": "Couleur texte secondaire",
        }
        help_texts = {
            "design_font_heading": (
                "Liste CSS de polices (ex: \"DM Sans\", \"Aptos\", \"Segoe UI\", sans-serif)."
            ),
            "design_font_body": (
                "Liste CSS de polices (ex: \"Nunito Sans\", \"Aptos\", \"Segoe UI\", sans-serif)."
            ),
            "design_color_primary": "Applique les boutons/actions principales.",
            "design_color_secondary": "Applique les actions secondaires et accents.",
            "design_color_background": "Fond global des pages.",
            "design_color_surface": "Fond des cartes et panneaux.",
            "design_color_border": "Couleur des bordures.",
            "design_color_text": "Couleur de texte principale.",
            "design_color_text_soft": "Couleur de texte secondaire/aide.",
        }
        widgets = {
            "design_font_heading": forms.TextInput(),
            "design_font_body": forms.TextInput(),
            "design_color_primary": forms.TextInput(attrs={"type": "color"}),
            "design_color_secondary": forms.TextInput(attrs={"type": "color"}),
            "design_color_background": forms.TextInput(attrs={"type": "color"}),
            "design_color_surface": forms.TextInput(attrs={"type": "color"}),
            "design_color_border": forms.TextInput(attrs={"type": "color"}),
            "design_color_text": forms.TextInput(attrs={"type": "color"}),
            "design_color_text_soft": forms.TextInput(attrs={"type": "color"}),
        }

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
        for field_name in ("design_font_heading", "design_font_body"):
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La police est obligatoire.")
            else:
                cleaned_data[field_name] = value
        return cleaned_data
