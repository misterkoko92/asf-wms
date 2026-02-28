from __future__ import annotations

from copy import deepcopy

from django.utils.text import slugify

from .design_tokens import DESIGN_TOKEN_DEFAULTS, normalize_priority_one_tokens

DEFAULT_STYLE_PRESET_KEY = "wms-default"
RECT_STYLE_PRESET_KEY = "wms-rect"
CONTRAST_STYLE_PRESET_KEY = "wms-contrast"
CUSTOM_STYLE_PRESET_PREFIX = "custom-"
CUSTOM_STYLE_NAME_MAX_LENGTH = 64

DESIGN_STYLE_FIELDS = (
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

DESIGN_STYLE_FIELD_DEFAULTS = {
    "design_font_h1": "DM Sans",
    "design_font_h2": "DM Sans",
    "design_font_h3": "DM Sans",
    "design_font_body": "Nunito Sans",
    "design_color_primary": "#6f9a8d",
    "design_color_secondary": "#e7c3a8",
    "design_color_background": "#f6f8f5",
    "design_color_surface": "#fffdf9",
    "design_color_border": "#d9e2dc",
    "design_color_text": "#2f3a36",
    "design_color_text_soft": "#5a6964",
}


def _compose_style(*, field_overrides=None, token_overrides=None):
    fields = dict(DESIGN_STYLE_FIELD_DEFAULTS)
    if isinstance(field_overrides, dict):
        for field_name in DESIGN_STYLE_FIELDS:
            if field_name in field_overrides:
                raw_value = str(field_overrides.get(field_name) or "").strip()
                if raw_value:
                    fields[field_name] = raw_value

    tokens_payload = dict(DESIGN_TOKEN_DEFAULTS)
    if isinstance(token_overrides, dict):
        tokens_payload.update(token_overrides)
    tokens = normalize_priority_one_tokens(tokens_payload)
    return {
        "fields": fields,
        "tokens": tokens,
    }


def _style_preset(key, label, description, *, field_overrides=None, token_overrides=None):
    payload = _compose_style(field_overrides=field_overrides, token_overrides=token_overrides)
    payload.update(
        {
            "key": key,
            "label": label,
            "description": description,
            "is_custom": False,
        }
    )
    return payload


BUILTIN_STYLE_PRESETS = (
    _style_preset(
        DEFAULT_STYLE_PRESET_KEY,
        "WMS - Equilibre (actuel)",
        "Palette WMS standard avec densite et arrondi moderes.",
    ),
    _style_preset(
        RECT_STYLE_PRESET_KEY,
        "WMS - Rectangulaire",
        "Variante structuree, compacte et boutons plus angulaires.",
        field_overrides={
            "design_color_primary": "#2f6d5f",
            "design_color_secondary": "#d8c29f",
            "design_color_background": "#f4f6f4",
            "design_color_surface": "#ffffff",
            "design_color_border": "#c8d4cd",
            "design_color_text": "#1f2926",
            "design_color_text_soft": "#475651",
        },
        token_overrides={
            "density_mode": "dense",
            "btn_style_mode": "outlined",
            "btn_radius": 0,
            "input_radius": 0,
            "nav_item_radius": 0,
            "table_radius": 0,
            "card_radius": 6,
            "badge_radius": 6,
            "status_progress_bg": "#eaf2ff",
            "status_progress_border": "#bbcfef",
            "status_progress_text": "#1f467a",
        },
    ),
    _style_preset(
        CONTRAST_STYLE_PRESET_KEY,
        "WMS - Contraste doux",
        "Couleurs plus marquees avec interlignes confort et style soft.",
        field_overrides={
            "design_font_h1": "Manrope",
            "design_font_h2": "Manrope",
            "design_font_h3": "DM Sans",
            "design_color_primary": "#355f89",
            "design_color_secondary": "#edc77d",
            "design_color_background": "#f2f6fb",
            "design_color_surface": "#ffffff",
            "design_color_border": "#cad8e6",
            "design_color_text": "#1d2c3b",
            "design_color_text_soft": "#4a5d70",
        },
        token_overrides={
            "density_mode": "airy",
            "btn_style_mode": "soft",
            "btn_radius": 8,
            "input_radius": 8,
            "nav_item_radius": 8,
            "card_radius": 14,
            "badge_radius": 10,
            "line_height_body": "1.6",
            "font_weight_body": "500",
            "color_btn_primary_bg": "#355f89",
            "color_btn_primary_border": "#2a4e73",
            "color_btn_primary_text": "#f6fbff",
            "status_progress_bg": "#e4edf9",
            "status_progress_border": "#b5c9e6",
            "status_progress_text": "#2f5077",
        },
    ),
)


def get_builtin_style_presets():
    return [deepcopy(preset) for preset in BUILTIN_STYLE_PRESETS]


def get_builtin_style_preset_map():
    return {preset["key"]: deepcopy(preset) for preset in BUILTIN_STYLE_PRESETS}


def build_style_snapshot_from_runtime(runtime_settings):
    fields = {
        field_name: str(getattr(runtime_settings, field_name, DESIGN_STYLE_FIELD_DEFAULTS[field_name]))
        for field_name in DESIGN_STYLE_FIELDS
    }
    tokens = normalize_priority_one_tokens(getattr(runtime_settings, "design_tokens", {}))
    return {
        "fields": fields,
        "tokens": tokens,
    }


def normalize_custom_style_presets(raw_presets):
    if not isinstance(raw_presets, dict):
        return {}

    normalized = {}
    for raw_key, raw_payload in raw_presets.items():
        key = str(raw_key or "").strip().lower()
        if not key or not key.startswith(CUSTOM_STYLE_PRESET_PREFIX):
            continue
        if not isinstance(raw_payload, dict):
            continue

        label = str(raw_payload.get("label") or "").strip()[:CUSTOM_STYLE_NAME_MAX_LENGTH]
        if not label:
            continue
        description = str(raw_payload.get("description") or "").strip()[:180]

        fields_payload = raw_payload.get("fields", {})
        fields = dict(DESIGN_STYLE_FIELD_DEFAULTS)
        if isinstance(fields_payload, dict):
            for field_name in DESIGN_STYLE_FIELDS:
                if field_name in fields_payload:
                    value = str(fields_payload.get(field_name) or "").strip()
                    if value:
                        fields[field_name] = value

        tokens = normalize_priority_one_tokens(raw_payload.get("tokens", {}))
        normalized[key] = {
            "label": label,
            "description": description,
            "fields": fields,
            "tokens": tokens,
        }

    return normalized


def build_custom_style_preset_key(name, *, existing_keys):
    existing = {str(value).strip().lower() for value in existing_keys or []}
    base_slug = slugify(name or "") or "style"
    base_slug = base_slug[:48]
    base = f"{CUSTOM_STYLE_PRESET_PREFIX}{base_slug}"
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
