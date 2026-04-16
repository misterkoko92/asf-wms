from django import template
from django.utils import timezone

register = template.Library()

WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _normalize_value(value):
    if value is None:
        return None
    if hasattr(value, "hour"):
        return timezone.localtime(value) if timezone.is_aware(value) else value
    return value


@register.filter
def scan_date_short(value):
    value = _normalize_value(value)
    return value.strftime("%d/%m/%y") if value else "-"


@register.filter
def scan_datetime_short(value):
    value = _normalize_value(value)
    return value.strftime("%d/%m/%y %Hh%M") if value else "-"


@register.filter
def scan_date_weekday_short(value):
    value = _normalize_value(value)
    if not value:
        return "-"
    return f"{WEEKDAY_LABELS[value.weekday()]} {value.strftime('%d/%m/%y')}"
