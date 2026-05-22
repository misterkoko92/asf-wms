from __future__ import annotations

from wms.models import Destination


def format_destination_label(destination: Destination) -> str:
    city_label = destination.city
    if destination.iata_code:
        city_label = f"{city_label} ({destination.iata_code})"
    if destination.country:
        return f"{city_label}, {destination.country}"
    return city_label


def served_destination_queryset():
    return (
        Destination.objects.select_related("correspondent_contact")
        .filter(is_active=True, correspondent_contact__is_active=True)
        .order_by("city", "country", "iata_code", "id")
    )


def list_served_destination_options() -> list[dict[str, object]]:
    return [
        {
            "id": destination.id,
            "label": format_destination_label(destination),
            "country": destination.country,
            "iata_code": destination.iata_code,
        }
        for destination in served_destination_queryset()
    ]
