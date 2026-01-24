from .models import Location, Warehouse

def resolve_default_warehouse():
    return (
        Warehouse.objects.filter(code__iexact="REC").first()
        or Warehouse.objects.filter(name__iexact="Reception").first()
        or Warehouse.objects.order_by("name").first()
    )


def build_location_data():
    locations = list(
        Location.objects.select_related("warehouse").order_by(
            "warehouse__name", "zone", "aisle", "shelf"
        )
    )
    return [
        {"id": location.id, "label": str(location), "warehouse": location.warehouse.name}
        for location in locations
    ]
