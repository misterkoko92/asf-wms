from django.test import TestCase

from wms.import_services import get_or_create_location, import_warehouses
from wms.models import Location, Warehouse


class ImportLocationsTests(TestCase):
    def test_get_or_create_location_normalizes(self):
        location = get_or_create_location("Main", "a", "b", "c")
        self.assertIsNotNone(location)
        self.assertEqual(location.zone, "A")
        self.assertEqual(location.aisle, "B")
        self.assertEqual(location.shelf, "C")
        self.assertEqual(Location.objects.count(), 1)

    def test_import_warehouses_updates_code(self):
        Warehouse.objects.create(name="Main", code="OLD")
        rows = [{"name": "Main", "code": "NEW"}]
        created, updated, errors = import_warehouses(rows)
        self.assertEqual(errors, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        warehouse = Warehouse.objects.get(name="Main")
        self.assertEqual(warehouse.code, "NEW")
