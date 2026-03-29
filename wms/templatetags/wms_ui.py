from django import template
from django.forms.utils import flatatt
from django.utils.html import format_html

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


def _normalize_attr_map(attrs=None, **extra_attrs):
    normalized = {}
    for key, value in (attrs or {}).items():
        if value in (None, False, ""):
            continue
        normalized[key] = value
    for key, value in extra_attrs.items():
        if value in (None, False, ""):
            continue
        normalized[key] = value
    return normalized


def _normalize_attrs(attrs=None, **extra_attrs):
    normalized = _normalize_attr_map(attrs, **extra_attrs)
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
    field=None,
    name="",
    id="",
    label="",
    checked=False,
    help_text="",
    wide=False,
    extra_classes="",
    value="1",
    attrs=None,
):
    switch_name = name or getattr(field, "html_name", "") or getattr(field, "name", "")
    switch_id = id or (field.id_for_label if field else "")
    switch_label = label or getattr(field, "label", "")
    label_id = f"{switch_id}-label" if switch_id else ""
    help_id = f"{switch_id}-caption" if switch_id and help_text else ""
    input_attrs = _normalize_attr_map(
        attrs,
        role="switch",
        **{
            "class": "form-check-input",
            "id": switch_id or None,
            "aria-labelledby": label_id or None,
            "aria-describedby": help_id or None,
        },
    )
    if field:
        input_html = field.as_widget(attrs=input_attrs)
    else:
        checkbox_attrs = _normalize_attr_map(
            input_attrs,
            type="checkbox",
            name=switch_name or None,
            value=value,
            checked="checked" if _as_bool(checked) else None,
        )
        input_html = format_html("<input{}>", flatatt(checkbox_attrs))

    return {
        "input_html": input_html,
        "id": switch_id,
        "label": switch_label,
        "help_text": help_text,
        "label_id": label_id,
        "help_id": help_id,
        "wrapper_classes": _join_classes(
            "form-check",
            "form-switch",
            "scan-inline-switch",
            "scan-inline-switch-wide" if _as_bool(wide) else "",
            extra_classes,
        ),
    }


@register.inclusion_tag("wms/components/file_input.html")
def ui_file_input(
    field=None,
    name="",
    field_id="",
    accept="",
    required=False,
    multiple=False,
    extra_classes="",
    attrs=None,
):
    classes = _join_classes("form-control", "ui-comp-file-input", extra_classes)
    widget_attrs = _normalize_attr_map(
        attrs,
        accept=accept or None,
        required="required" if _as_bool(required) else None,
        multiple="multiple" if _as_bool(multiple) else None,
        **{"class": classes},
    )
    if field:
        return {
            "input_html": field.as_widget(attrs=widget_attrs),
        }

    input_attrs = _normalize_attr_map(
        widget_attrs,
        type="file",
        id=field_id or None,
        name=name or None,
    )
    return {
        "input_html": format_html("<input{}>", flatatt(input_attrs)),
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
