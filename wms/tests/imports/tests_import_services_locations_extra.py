from django.test import TestCase

from wms.import_services_locations import (
    get_or_create_location,
    import_locations,
    import_warehouses,
    resolve_listing_location,
)
from wms.models import Location, RackColor, Warehouse


class ImportLocationsExtraTests(TestCase):
    def test_get_or_create_location_returns_none_when_incomplete(self):
        self.assertIsNone(get_or_create_location("WH", "A", "01", None))
        self.assertEqual(Location.objects.count(), 0)

    def test_resolve_listing_location_handles_none_incomplete_and_create(self):
        self.assertIsNone(resolve_listing_location({}, default_warehouse=None))

        with self.assertRaisesMessage(ValueError, "Emplacement incomplet"):
            resolve_listing_location(
                {"warehouse": "WH", "zone": "A", "aisle": "01"},
                default_warehouse=None,
            )

        default_warehouse = Warehouse.objects.create(name="Main")
        location = resolve_listing_location(
            {"zone": "a", "aisle": "01", "shelf": "b"},
            default_warehouse=default_warehouse,
        )
        self.assertEqual(location.warehouse.name, "Main")
        self.assertEqual(location.zone, "A")
        self.assertEqual(location.aisle, "01")
        self.assertEqual(location.shelf, "B")

    def test_import_locations_creates_updates_and_records_errors(self):
        warehouse = Warehouse.objects.create(name="Main")
        existing = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
            notes="OLD",
        )
        rows = [
            {"warehouse": "Main", "zone": "a", "aisle": "01", "shelf": "001", "notes": "NEW"},
            {"warehouse": "Main", "zone": "b", "aisle": "02", "shelf": "002", "notes": "ok", "rack_color": "Red"},
            {"warehouse": "Main", "zone": "C"},
            {"warehouse": "", "zone": "", "aisle": "", "shelf": ""},
        ]

        created, updated, errors = import_locations(rows)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Champs requis: entrepôt, rack, étagère, bac.", errors[0])

        existing.refresh_from_db()
        self.assertEqual(existing.notes, "NEW")
        created_location = Location.objects.get(zone="B", aisle="02", shelf="002")
        self.assertEqual(created_location.notes, "ok")
        rack_color = RackColor.objects.get(warehouse=warehouse, zone="B")
        self.assertEqual(rack_color.color, "Red")

    def test_import_warehouses_creates_updates_and_errors(self):
        Warehouse.objects.create(name="Main", code="OLD")
        rows = [
            {"name": "Main", "code": "NEW"},
            {"name": "Secondary", "code": ""},
            {"name": "", "code": "X"},
            {"name": "Main", "code": None},
            {"name": "   ", "code": "   "},
        ]

        created, updated, errors = import_warehouses(rows)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Nom entrepôt requis.", errors[0])
        self.assertEqual(Warehouse.objects.get(name="Main").code, "NEW")
        self.assertEqual(Warehouse.objects.get(name="Secondary").code, "")
