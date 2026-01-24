from .import_services_common import _row_is_empty
from .import_utils import get_value, parse_str
from .models import Location, RackColor, Warehouse
from .text_utils import normalize_upper

def get_or_create_location(warehouse_name, zone, aisle, shelf):
    if not all([warehouse_name, zone, aisle, shelf]):
        return None
    warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
    zone = normalize_upper(zone)
    aisle = normalize_upper(aisle)
    shelf = normalize_upper(shelf)
    location, _ = Location.objects.get_or_create(
        warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
    )
    return location


def resolve_listing_location(row, default_warehouse):
    warehouse_name = parse_str(row.get("warehouse")) or (
        default_warehouse.name if default_warehouse else None
    )
    zone = parse_str(row.get("zone"))
    aisle = parse_str(row.get("aisle"))
    shelf = parse_str(row.get("shelf"))
    if any([zone, aisle, shelf]):
        if not all([warehouse_name, zone, aisle, shelf]):
            raise ValueError("Emplacement incomplet (entrepot/rack/etagere/bac).")
        warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
        zone = normalize_upper(zone)
        aisle = normalize_upper(aisle)
        shelf = normalize_upper(shelf)
        location, _ = Location.objects.get_or_create(
            warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
        )
        return location
    return None


def import_locations(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            warehouse_name = parse_str(get_value(row, "warehouse", "entrepot"))
            zone = parse_str(get_value(row, "zone", "rack"))
            aisle = parse_str(get_value(row, "aisle", "etagere"))
            shelf = parse_str(get_value(row, "shelf", "bac"))
            notes = parse_str(get_value(row, "notes", "note"))
            rack_color = parse_str(get_value(row, "rack_color", "couleur_rack"))
            if not all([warehouse_name, zone, aisle, shelf]):
                raise ValueError("Champs requis: entrepot, rack, etagere, bac.")
            warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
            zone = normalize_upper(zone)
            aisle = normalize_upper(aisle)
            shelf = normalize_upper(shelf)
            location, was_created = Location.objects.get_or_create(
                warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
            )
            if notes is not None and location.notes != notes:
                location.notes = notes
                location.save(update_fields=["notes"])
                updated += 1 if not was_created else 0
            if was_created:
                created += 1
            if rack_color:
                RackColor.objects.update_or_create(
                    warehouse=warehouse,
                    zone=zone,
                    defaults={"color": rack_color},
                )
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors


def import_warehouses(rows):
    created = 0
    updated = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        if _row_is_empty(row):
            continue
        try:
            name = parse_str(get_value(row, "name", "warehouse", "entrepot"))
            code = parse_str(get_value(row, "code"))
            if not name:
                raise ValueError("Nom entrepot requis.")
            warehouse, was_created = Warehouse.objects.get_or_create(
                name=name, defaults={"code": code or ""}
            )
            if not was_created and code is not None and warehouse.code != code:
                warehouse.code = code
                warehouse.save(update_fields=["code"])
                updated += 1
            if was_created:
                created += 1
        except ValueError as exc:
            errors.append(f"Ligne {index}: {exc}")
    return created, updated, errors
