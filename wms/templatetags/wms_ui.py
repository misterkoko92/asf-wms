from django import template
from django.forms.utils import flatatt

from wms.status_badges import build_status_class

register = template.Library()


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _join_classes(*parts):
    classes = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, list | tuple):
            for item in part:
                if item:
                    classes.extend(str(item).split())
            continue
        classes.extend(str(part).split())
    return " ".join(classes)


def _normalize_attrs(attrs=None, **extra_attrs):
    normalized = {}
    for key, value in (attrs or {}).items():
        if value in (None, False, ""):
            continue
        normalized[key] = value
    for key, value in extra_attrs.items():
        if value in (None, False, ""):
            continue
        normalized[key] = value
    return flatatt(normalized)


def _secure_rel(target, rel):
    rel_tokens = [token for token in str(rel or "").split() if token]
    if target == "_blank":
        for token in ("noopener", "noreferrer"):
            if token not in rel_tokens:
                rel_tokens.append(token)
    return " ".join(rel_tokens)


@register.inclusion_tag("wms/components/button.html")
def ui_button(
    label,
    href="",
    button_type="button",
    variant="primary",
    size="",
    extra_classes="",
    target="",
    rel="",
    attrs=None,
):
    classes = _join_classes(
        "btn",
        f"btn-{variant or 'primary'}",
        f"btn-{size}" if size else "",
        extra_classes,
    )
    rel_value = _secure_rel(target, rel)
    return {
        "label": label,
        "href": href,
        "button_type": button_type or "button",
        "classes": classes,
        "attrs": _normalize_attrs(attrs, target=target or None, rel=rel_value or None),
    }


@register.inclusion_tag("wms/components/alert.html")
def ui_alert(
    title="",
    body="",
    tone="info",
    extra_classes="",
    attrs=None,
):
    return {
        "title": title,
        "body": body,
        "classes": _join_classes("scan-message", tone or "info", "ui-comp-alert", extra_classes),
        "attrs": _normalize_attrs(attrs, role="alert"),
    }


@register.inclusion_tag("wms/components/field.html")
def ui_field(
    field_id="",
    label="",
    field_html="",
    help_text="",
    errors=None,
    extra_classes="",
    attrs=None,
    label_class="form-label",
    help_class="form-text",
    error_class="text-danger small",
):
    return {
        "field_id": field_id,
        "label": label,
        "field_html": field_html,
        "help_text": help_text,
        "errors": errors or [],
        "wrapper_classes": _join_classes("scan-field", extra_classes),
        "attrs": _normalize_attrs(attrs),
        "label_class": label_class,
        "help_class": help_class,
        "error_class": error_class,
    }


@register.inclusion_tag("wms/components/switch.html")
def ui_switch(
    name,
    id,
    label,
    checked=False,
    help_text="",
    wide=False,
    extra_classes="",
    value="1",
    attrs=None,
):
    return {
        "name": name,
        "id": id,
        "label": label,
        "checked": _as_bool(checked),
        "help_text": help_text,
        "value": value,
        "wrapper_classes": _join_classes(
            "form-check",
            "form-switch",
            "scan-inline-switch",
            "scan-inline-switch-wide" if _as_bool(wide) else "",
            extra_classes,
        ),
        "attrs": _normalize_attrs(attrs),
    }


@register.inclusion_tag("wms/components/status_badge.html")
def ui_status_badge(
    label="",
    status_value="",
    domain="",
    is_disputed=False,
    extra_classes="",
    base_class="ui-comp-status-pill",
    attrs=None,
):
    classes = _join_classes(
        build_status_class(
            status_value,
            domain=domain,
            is_disputed=_as_bool(is_disputed),
            base_class=base_class,
        ),
        extra_classes,
    )
    return {
        "label": label or status_value,
        "classes": classes,
        "attrs": _normalize_attrs(attrs),
    }
