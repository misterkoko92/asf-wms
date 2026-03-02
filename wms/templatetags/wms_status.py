from django import template

from wms.status_badges import build_status_class, resolve_status_tone

register = template.Library()


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@register.simple_tag
def status_tone(status_value, domain="", is_disputed=False):
    return resolve_status_tone(
        status_value,
        domain=domain,
        is_disputed=_as_bool(is_disputed),
    )


@register.simple_tag
def status_pill_class(status_value, domain="", is_disputed=False):
    return build_status_class(
        status_value,
        domain=domain,
        is_disputed=_as_bool(is_disputed),
        base_class="ui-comp-status-pill",
    )


@register.simple_tag
def status_portal_badge_class(status_value, domain="", is_disputed=False):
    return build_status_class(
        status_value,
        domain=domain,
        is_disputed=_as_bool(is_disputed),
        base_class="portal-badge",
    )
