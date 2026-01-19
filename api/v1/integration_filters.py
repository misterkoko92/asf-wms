from django.db.models import Q
from django.utils import timezone


def _normalize_param(params, key):
    return (params.get(key) or "").strip()


def apply_integration_shipment_filters(queryset, params):
    status_value = _normalize_param(params, "status")
    if status_value:
        queryset = queryset.filter(status=status_value)
    destination = _normalize_param(params, "destination")
    if destination:
        queryset = queryset.filter(
            Q(destination__iata_code__iexact=destination)
            | Q(destination__city__icontains=destination)
        )
    since = _normalize_param(params, "since")
    if since:
        try:
            since_dt = timezone.datetime.fromisoformat(since)
        except ValueError:
            return queryset
        if timezone.is_naive(since_dt):
            since_dt = timezone.make_aware(since_dt)
        queryset = queryset.filter(created_at__gte=since_dt)
    return queryset


def apply_integration_destination_filters(queryset, params):
    active_only = _normalize_param(params, "active")
    if active_only:
        return queryset.filter(is_active=True)
    return queryset


def apply_integration_event_filters(queryset, params):
    direction = _normalize_param(params, "direction")
    if direction:
        queryset = queryset.filter(direction=direction)
    status_value = _normalize_param(params, "status")
    if status_value:
        queryset = queryset.filter(status=status_value)
    source = _normalize_param(params, "source")
    if source:
        queryset = queryset.filter(source=source)
    event_type = _normalize_param(params, "event_type")
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    return queryset
