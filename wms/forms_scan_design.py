import re

from django import forms

from .design_tokens import (
    DESIGN_TOKEN_DEFAULTS,
    DESIGN_TOKEN_FAMILY_DEFINITIONS,
    DESIGN_TOKEN_FAMILY_FIELDS,
    DESIGN_TOKEN_FIELD_TO_KEY,
    DESIGN_TOKEN_SPECS,
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


def _build_token_field(spec):
    kind = spec["kind"]
    label = spec["label"]
    help_text = spec["help_text"]

    if kind == "choice":
        return forms.ChoiceField(
            required=False,
            choices=spec["choices"],
            label=label,
            help_text=help_text,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

    if kind == "int":
        return forms.IntegerField(
            required=False,
            min_value=spec["min"],
            max_value=spec["max"],
            label=label,
            help_text=help_text,
            widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
        )

    if kind == "color":
        return forms.CharField(
            required=False,
            max_length=16,
            label=label,
            help_text=help_text,
            widget=forms.TextInput(attrs=_color_widget_attrs()),
        )

    return forms.CharField(
        required=False,
        max_length=spec.get("max_length", 120),
        label=label,
        help_text=help_text,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


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
    TOKEN_FIELD_TO_KEY = DESIGN_TOKEN_FIELD_TO_KEY
    TOKEN_FIELDS = tuple(TOKEN_FIELD_TO_KEY.keys())
    PREVIEW_FIELDS = DESIGN_FIELDS + TOKEN_FIELDS
    RUNTIME_FIELDS = (
        "scan_bootstrap_enabled",
        "design_font_heading",
        *DESIGN_FIELDS,
        "design_tokens",
    )

    SECTION_DEFINITIONS = DESIGN_TOKEN_FAMILY_DEFINITIONS
    SECTION_STATIC_FIELDS = {
        "foundations": ("scan_bootstrap_enabled",),
        "typography": ("design_font_h1", "design_font_h2", "design_font_h3", "design_font_body"),
        "global_colors": (
            "design_color_primary",
            "design_color_secondary",
            "design_color_background",
            "design_color_surface",
            "design_color_border",
            "design_color_text",
            "design_color_text_soft",
        ),
        "buttons": (),
        "inputs": (),
        "cards": (),
        "navigation": (),
        "tables": (),
        "business_states": (),
    }
    DEFAULT_OPEN_SECTIONS = {"foundations", "global_colors", "buttons"}
    PREVIEW_FIELD_META = {
        "design_color_primary": {"css_var": "--preview-primary"},
        "design_color_secondary": {"css_var": "--preview-secondary"},
        "design_color_background": {"css_var": "--preview-bg"},
        "design_color_surface": {"css_var": "--preview-surface"},
        "design_color_border": {"css_var": "--preview-border"},
        "design_color_text": {"css_var": "--preview-text"},
        "design_color_text_soft": {"css_var": "--preview-text-soft"},
        "design_font_h1": {"css_var": "--preview-font-h1"},
        "design_font_h2": {"css_var": "--preview-font-h2"},
        "design_font_h3": {"css_var": "--preview-font-h3"},
        "design_font_body": {"css_var": "--preview-font-body"},
        "design_density_mode": {"dataset_attr": "densityMode"},
        "design_btn_style_mode": {"dataset_attr": "btnStyleMode"},
        "design_text_transform_heading": {"dataset_attr": "headingTransform"},
    }

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
            "design_font_h1": "Police du titre principal.",
            "design_font_h2": "Police des titres de section.",
            "design_font_h3": "Police des sous-titres.",
            "design_font_body": "Police du texte courant.",
            "design_color_primary": "Couleur des actions principales.",
            "design_color_secondary": "Couleur des actions secondaires.",
            "design_color_background": "Fond global des pages.",
            "design_color_surface": "Fond des cartes et panneaux.",
            "design_color_border": "Couleur des bordures.",
            "design_color_text": "Couleur de texte principale.",
            "design_color_text_soft": "Couleur du texte secondaire.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["scan_bootstrap_enabled"].widget = forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        )

        base_choices = list(self.FONT_CHOICES)
        base_choice_values = {value for value, _label in base_choices}
        for field_name in self.FONT_FIELDS:
            self.fields[field_name].widget = forms.Select(
                choices=base_choices, attrs={"class": "form-select"}
            )

        if self.instance and getattr(self.instance, "pk", None):
            for field_name in self.FONT_FIELDS:
                current = getattr(self.instance, field_name, "")
                normalized = _normalize_font_name(current)
                if normalized and normalized not in base_choice_values:
                    self.fields[field_name].widget.choices = base_choices + [
                        (normalized, f"{normalized} (actuelle)")
                    ]
                self.initial[field_name] = normalized

        for field_name in self.COLOR_FIELDS:
            self.fields[field_name].widget = forms.TextInput(attrs=_color_widget_attrs())

        for field_name, token_key in self.TOKEN_FIELD_TO_KEY.items():
            if field_name not in self.fields:
                self.fields[field_name] = _build_token_field(DESIGN_TOKEN_SPECS[token_key])

        tokens = normalize_priority_one_tokens(
            getattr(self.instance, "design_tokens", DESIGN_TOKEN_DEFAULTS)
        )
        for field_name, token_key in self.TOKEN_FIELD_TO_KEY.items():
            self.initial[field_name] = tokens[token_key]

        self._apply_preview_metadata()

    def _apply_preview_metadata(self):
        for field_name, field in self.fields.items():
            field.widget.attrs["data-design-field"] = "1"

            preview_meta = dict(self.PREVIEW_FIELD_META.get(field_name, {}))
            token_key = self.TOKEN_FIELD_TO_KEY.get(field_name)
            if token_key:
                spec = DESIGN_TOKEN_SPECS[token_key]
                if spec.get("preview_var") and "css_var" not in preview_meta:
                    preview_meta["css_var"] = spec["preview_var"]
                if spec.get("preview_unit"):
                    preview_meta["preview_unit"] = spec["preview_unit"]

            if preview_meta.get("css_var"):
                field.widget.attrs["data-preview-css-var"] = preview_meta["css_var"]
            if preview_meta.get("preview_unit"):
                field.widget.attrs["data-preview-unit"] = preview_meta["preview_unit"]
            if preview_meta.get("dataset_attr"):
                field.widget.attrs["data-preview-attr"] = preview_meta["dataset_attr"]

    def _normalize_color_field(self, field_name, value, *, fallback):
        resolved = (value or "").strip()
        if not resolved:
            resolved = fallback
        if not HEX_COLOR_RE.match(resolved):
            self.add_error(field_name, "Utilisez le format hexadécimal #RRGGBB.")
            return fallback
        return resolved.lower()

    def clean(self):
        cleaned_data = super().clean()

        for field_name in self.COLOR_FIELDS:
            fallback = self.initial.get(field_name, "")
            value = cleaned_data.get(field_name)
            normalized = self._normalize_color_field(field_name, value, fallback=fallback)
            cleaned_data[field_name] = normalized

        for field_name in self.FONT_FIELDS:
            value = (cleaned_data.get(field_name) or "").strip()
            if not value:
                self.add_error(field_name, "La police est obligatoire.")
                continue
            cleaned_data[field_name] = _normalize_font_name(value)

        for field_name, token_key in self.TOKEN_FIELD_TO_KEY.items():
            spec = DESIGN_TOKEN_SPECS[token_key]
            fallback = self.initial.get(field_name, DESIGN_TOKEN_DEFAULTS[token_key])
            value = cleaned_data.get(field_name)

            if spec["kind"] == "choice":
                resolved = str(value or "").strip().lower()
                if not resolved:
                    resolved = str(fallback).strip().lower()
                allowed = {choice for choice, _label in spec["choices"]}
                if resolved not in allowed:
                    self.add_error(field_name, "Selection invalide.")
                    continue
                cleaned_data[field_name] = resolved
                continue

            if spec["kind"] == "int":
                if value in ("", None):
                    resolved = int(fallback)
                else:
                    try:
                        resolved = int(value)
                    except (TypeError, ValueError):
                        self.add_error(field_name, "Entrez un nombre entier.")
                        continue
                cleaned_data[field_name] = max(spec["min"], min(spec["max"], resolved))
                continue

            if spec["kind"] == "color":
                cleaned_data[field_name] = self._normalize_color_field(
                    field_name, value, fallback=str(fallback)
                )
                continue

            resolved = str(value or "").strip()
            if not resolved:
                resolved = str(fallback).strip()
            cleaned_data[field_name] = resolved[: spec.get("max_length", 120)]

        return cleaned_data

    def save(self, commit=True):
        runtime_settings = super().save(commit=False)
        tokens_payload = {
            token_key: self.cleaned_data.get(field_name)
            for field_name, token_key in self.TOKEN_FIELD_TO_KEY.items()
        }
        runtime_settings.design_tokens = normalize_priority_one_tokens(tokens_payload)
        if commit:
            runtime_settings.save()
        return runtime_settings

    def get_section_context(self):
        sections = []
        for key, label, description, default_open in self.SECTION_DEFINITIONS:
            field_names = [
                *self.SECTION_STATIC_FIELDS.get(key, ()),
                *DESIGN_TOKEN_FAMILY_FIELDS.get(key, ()),
            ]
            bound_fields = [self[field_name] for field_name in field_names if field_name in self.fields]
            sections.append(
                {
                    "key": key,
                    "label": label,
                    "description": description,
                    "default_open": default_open,
                    "fields": bound_fields,
                }
            )
        return sections
