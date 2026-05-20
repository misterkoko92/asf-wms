from __future__ import annotations

from wms.models import Destination


def served_destination_queryset():
    return (
        Destination.objects.select_related("correspondent_contact")
        .filter(is_active=True, correspondent_contact__is_active=True)
        .order_by("city", "iata_code", "id")
    )


def list_served_destination_options() -> list[dict[str, object]]:
    return [
        {
            "id": destination.id,
            "label": str(destination),
            "country": destination.country,
            "iata_code": destination.iata_code,
        }
        for destination in served_destination_queryset()
    ]
