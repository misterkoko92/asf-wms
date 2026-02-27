import re

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DENSITY_MODE_CHOICES = (
    ("dense", "Dense"),
    ("standard", "Standard"),
    ("airy", "Aere"),
)

BTN_STYLE_MODE_CHOICES = (
    ("flat", "Flat"),
    ("soft", "Soft"),
    ("elevated", "Elevated"),
    ("outlined", "Outlined"),
)

PRIORITY_ONE_TOKEN_DEFAULTS = {
    "density_mode": "standard",
    "btn_style_mode": "flat",
    "btn_radius": 10,
    "btn_height_md": 42,
    "btn_shadow": "none",
    "card_radius": 16,
    "card_shadow": "none",
    "input_height": 42,
    "input_radius": 10,
    "nav_item_active_bg": "#ddebe6",
    "nav_item_active_text": "#2f3a36",
    "dropdown_shadow": "none",
    "table_row_hover_bg": "#e7f1ec",
    "color_btn_success_bg": "#e8f4ee",
    "color_btn_success_text": "#2d5e46",
    "color_btn_success_border": "#b8d6c8",
    "color_btn_warning_bg": "#fbf2e7",
    "color_btn_warning_text": "#715829",
    "color_btn_warning_border": "#e5d0a6",
    "color_btn_danger_bg": "#faece7",
    "color_btn_danger_text": "#7b3030",
    "color_btn_danger_border": "#dfb0b0",
}

PRIORITY_ONE_TOKEN_FIELD_TO_KEY = {
    "design_density_mode": "density_mode",
    "design_btn_style_mode": "btn_style_mode",
    "design_btn_radius": "btn_radius",
    "design_btn_height_md": "btn_height_md",
    "design_btn_shadow": "btn_shadow",
    "design_card_radius": "card_radius",
    "design_card_shadow": "card_shadow",
    "design_input_height": "input_height",
    "design_input_radius": "input_radius",
    "design_nav_item_active_bg": "nav_item_active_bg",
    "design_nav_item_active_text": "nav_item_active_text",
    "design_dropdown_shadow": "dropdown_shadow",
    "design_table_row_hover_bg": "table_row_hover_bg",
    "design_color_btn_success_bg": "color_btn_success_bg",
    "design_color_btn_success_text": "color_btn_success_text",
    "design_color_btn_success_border": "color_btn_success_border",
    "design_color_btn_warning_bg": "color_btn_warning_bg",
    "design_color_btn_warning_text": "color_btn_warning_text",
    "design_color_btn_warning_border": "color_btn_warning_border",
    "design_color_btn_danger_bg": "color_btn_danger_bg",
    "design_color_btn_danger_text": "color_btn_danger_text",
    "design_color_btn_danger_border": "color_btn_danger_border",
}

PRIORITY_ONE_TOKEN_COLOR_KEYS = (
    "nav_item_active_bg",
    "nav_item_active_text",
    "table_row_hover_bg",
    "color_btn_success_bg",
    "color_btn_success_text",
    "color_btn_success_border",
    "color_btn_warning_bg",
    "color_btn_warning_text",
    "color_btn_warning_border",
    "color_btn_danger_bg",
    "color_btn_danger_text",
    "color_btn_danger_border",
)

PRIORITY_ONE_TOKEN_INT_KEYS = (
    "btn_radius",
    "btn_height_md",
    "card_radius",
    "input_height",
    "input_radius",
)

PRIORITY_ONE_TOKEN_SHADOW_KEYS = (
    "btn_shadow",
    "card_shadow",
    "dropdown_shadow",
)


def normalize_priority_one_tokens(raw_tokens):
    normalized = dict(PRIORITY_ONE_TOKEN_DEFAULTS)
    if not isinstance(raw_tokens, dict):
        return normalized

    density_mode = (raw_tokens.get("density_mode") or "").strip().lower()
    if density_mode in {"dense", "standard", "airy"}:
        normalized["density_mode"] = density_mode

    btn_style_mode = (raw_tokens.get("btn_style_mode") or "").strip().lower()
    if btn_style_mode in {"flat", "soft", "elevated", "outlined"}:
        normalized["btn_style_mode"] = btn_style_mode

    for key in PRIORITY_ONE_TOKEN_INT_KEYS:
        value = raw_tokens.get(key)
        try:
            resolved = int(value)
        except (TypeError, ValueError):
            continue
        normalized[key] = max(0, min(120, resolved))

    for key in PRIORITY_ONE_TOKEN_COLOR_KEYS:
        value = (raw_tokens.get(key) or "").strip()
        if HEX_COLOR_RE.match(value):
            normalized[key] = value.lower()

    for key in PRIORITY_ONE_TOKEN_SHADOW_KEYS:
        value = (raw_tokens.get(key) or "").strip()
        if value:
            normalized[key] = value[:120]

    return normalized


def density_factor_for_mode(mode):
    return {
        "dense": 0.9,
        "standard": 1.0,
        "airy": 1.12,
    }.get((mode or "").strip().lower(), 1.0)
