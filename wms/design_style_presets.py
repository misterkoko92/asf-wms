from __future__ import annotations

from copy import deepcopy

from django.utils.text import slugify

from .design_tokens import DESIGN_TOKEN_DEFAULTS, normalize_priority_one_tokens

DEFAULT_STYLE_PRESET_KEY = "wms-default"
RECT_STYLE_PRESET_KEY = "wms-rect"
CONTRAST_STYLE_PRESET_KEY = "wms-contrast"
STREAM_STYLE_PRESET_KEY = "wms-stream"
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
    _style_preset(
        STREAM_STYLE_PRESET_KEY,
        "WMS - Stream moderne",
        "Inspire de Stream UI Kit: contraste violet, accent turquoise et surfaces claires.",
        field_overrides={
            "design_font_h1": "Manrope",
            "design_font_h2": "Manrope",
            "design_font_h3": "Source Sans 3",
            "design_font_body": "Source Sans 3",
            "design_color_primary": "#5c2b80",
            "design_color_secondary": "#00c9a7",
            "design_color_background": "#f7f9fc",
            "design_color_surface": "#ffffff",
            "design_color_border": "#dde6f2",
            "design_color_text": "#1f2633",
            "design_color_text_soft": "#5f6c7b",
        },
        token_overrides={
            "density_mode": "standard",
            "line_height_body": "1.6",
            "font_weight_heading": "700",
            "font_weight_body": "400",
            "letter_spacing_heading": "0.01em",
            "letter_spacing_body": "0em",
            "btn_style_mode": "elevated",
            "btn_radius": 120,
            "btn_height_md": 40,
            "btn_border_width": 1,
            "btn_padding_x": 18,
            "btn_font_size": 14,
            "btn_shadow": "0 6px 14px rgba(55, 125, 255, 0.18)",
            "color_btn_primary_bg": "#5c2b80",
            "color_btn_primary_text": "#f9f7ff",
            "color_btn_primary_border": "#4b2269",
            "color_btn_secondary_bg": "#e6fbf7",
            "color_btn_secondary_text": "#006e62",
            "color_btn_secondary_border": "#8de6d8",
            "color_surface_alt": "#eef4fb",
            "color_panel": "#f8fbff",
            "color_link": "#377dff",
            "color_link_hover": "#2f6de0",
            "color_focus_ring": "#377dff",
            "color_disabled_bg": "#f1f5fb",
            "color_disabled_text": "#8898ad",
            "color_disabled_border": "#d8e2ef",
            "input_height": 42,
            "input_radius": 12,
            "input_bg": "#ffffff",
            "input_border": "#d9e4f2",
            "input_text": "#1f2633",
            "input_placeholder": "#6e7b8c",
            "input_focus_border": "#5c2b80",
            "input_focus_shadow": "0 0 0 0.2rem rgba(92, 43, 128, 0.18)",
            "card_radius": 18,
            "card_border_color": "#dde6f2",
            "card_bg": "#ffffff",
            "card_shadow": "0 12px 30px rgba(15, 33, 61, 0.08)",
            "card_header_bg": "#f5f8fd",
            "card_header_text": "#1f2633",
            "nav_item_bg": "#ffffff",
            "nav_item_text": "#1f2633",
            "nav_item_border": "#d9e4f2",
            "nav_item_hover_bg": "#f4f0fb",
            "nav_item_hover_text": "#4b2269",
            "nav_item_active_bg": "#ece3f8",
            "nav_item_active_text": "#3b1c52",
            "nav_item_radius": 32,
            "nav_item_padding_x": 12,
            "nav_item_padding_y": 7,
            "dropdown_bg": "#ffffff",
            "dropdown_border": "#d9e4f2",
            "dropdown_shadow": "0 12px 26px rgba(15, 33, 61, 0.12)",
            "dropdown_item_font_weight": "600",
            "dropdown_item_padding_y": 8,
            "dropdown_item_padding_x": 10,
            "table_header_bg": "#f5f8fd",
            "table_header_text": "#32445d",
            "table_header_letter_spacing": "0.04em",
            "table_header_padding_x": 10,
            "table_row_bg": "#ffffff",
            "table_row_alt_bg": "#fbfdff",
            "table_row_hover_bg": "#f0f6ff",
            "table_cell_padding_y": 8,
            "table_cell_padding_x": 10,
            "table_border_color": "#dce7f5",
            "table_radius": 12,
            "badge_radius": 999,
            "color_btn_success_bg": "#e8fbf6",
            "color_btn_success_text": "#0f6a5d",
            "color_btn_success_border": "#9ce3d6",
            "color_btn_success_hover_bg": "#dcf6ef",
            "color_btn_success_active_bg": "#cdeee5",
            "color_btn_warning_bg": "#fff4e5",
            "color_btn_warning_text": "#7d5a1f",
            "color_btn_warning_border": "#f0cb95",
            "color_btn_warning_hover_bg": "#ffeacc",
            "color_btn_warning_active_bg": "#fde0b4",
            "color_btn_danger_bg": "#fdebec",
            "color_btn_danger_text": "#8a2f3d",
            "color_btn_danger_border": "#ebb0ba",
            "color_btn_danger_hover_bg": "#f9dce0",
            "color_btn_danger_active_bg": "#f4c8cf",
            "status_ready_bg": "#e8fbf6",
            "status_ready_text": "#0f6a5d",
            "status_ready_border": "#9ce3d6",
            "status_progress_bg": "#e8f1ff",
            "status_progress_text": "#2857a4",
            "status_progress_border": "#b4ccf5",
            "status_warning_bg": "#fff4e5",
            "status_warning_text": "#7d5a1f",
            "status_warning_border": "#f0cb95",
            "status_error_bg": "#fdebec",
            "status_error_text": "#8a2f3d",
            "status_error_border": "#ebb0ba",
            "status_info_bg": "#eef2ff",
            "status_info_text": "#3d4f96",
            "status_info_border": "#bcc8ee",
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
