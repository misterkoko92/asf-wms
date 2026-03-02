from django.utils.html import format_html

from .status_badges import (
    BADGE_TONE_ERROR,
    BADGE_TONE_PROGRESS,
    BADGE_TONE_READY,
    BADGE_TONE_WARNING,
    resolve_status_tone,
)

_ADMIN_TONE_COLORS = {
    BADGE_TONE_READY: {
        "background": "#e8f4ee",
        "border": "#b8d6c8",
        "text": "#2d5e46",
    },
    BADGE_TONE_PROGRESS: {
        "background": "#eef3fb",
        "border": "#b4cbe7",
        "text": "#274d7f",
    },
    BADGE_TONE_WARNING: {
        "background": "#fbf2e7",
        "border": "#e5d0a6",
        "text": "#715829",
    },
    BADGE_TONE_ERROR: {
        "background": "#faece7",
        "border": "#dfb0b0",
        "text": "#7b3030",
    },
}

_PILL_STYLE = (
    "display:inline-block;"
    "padding:2px 8px;"
    "border-radius:999px;"
    "border:1px solid {border};"
    "background:{background};"
    "color:{text};"
    "font-weight:700;"
    "line-height:1.3;"
    "font-size:12px;"
    "white-space:nowrap;"
)


def render_admin_status_badge(*, status_value, label="", domain="", is_disputed=False):
    tone = resolve_status_tone(
        status_value,
        domain=domain,
        is_disputed=is_disputed,
    )
    colors = _ADMIN_TONE_COLORS.get(tone, _ADMIN_TONE_COLORS[BADGE_TONE_PROGRESS])
    safe_label = str(label or status_value or "-")
    return format_html(
        '<span style="{}">{}</span>',
        _PILL_STYLE.format(**colors),
        safe_label,
    )
