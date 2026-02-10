from django.test import TestCase

from wms.models import Location, Warehouse
from wms.scan_location_helpers import build_location_data, resolve_default_warehouse


class ScanLocationHelpersTests(TestCase):
    def test_resolve_default_warehouse_prefers_code(self):
        Warehouse.objects.create(name="Alpha", code="A")
        preferred = Warehouse.objects.create(name="Reception", code="REC")
        self.assertEqual(resolve_default_warehouse().id, preferred.id)

    def test_resolve_default_warehouse_falls_back_to_name(self):
        preferred = Warehouse.objects.create(name="Reception", code="R")
        Warehouse.objects.create(name="Zulu", code="Z")
        self.assertEqual(resolve_default_warehouse().id, preferred.id)

    def test_resolve_default_warehouse_uses_first_by_name(self):
        first = Warehouse.objects.create(name="Alpha", code="A")
        Warehouse.objects.create(name="Beta", code="B")
        self.assertEqual(resolve_default_warehouse().id, first.id)

    def test_build_location_data_returns_sorted_rows(self):
        wh_b = Warehouse.objects.create(name="Beta", code="B")
        wh_a = Warehouse.objects.create(name="Alpha", code="A")
        loc_b = Location.objects.create(
            warehouse=wh_b, zone="B", aisle="01", shelf="001"
        )
        loc_a = Location.objects.create(
            warehouse=wh_a, zone="A", aisle="01", shelf="001"
        )
        data = build_location_data()
        self.assertEqual(data[0]["label"], str(loc_a))
        self.assertEqual(data[1]["label"], str(loc_b))
