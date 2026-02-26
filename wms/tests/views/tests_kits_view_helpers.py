from datetime import date

from django.test import TestCase

from wms.kits_view_helpers import build_kits_view_rows
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    Location,
    Product,
    ProductCategory,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    Warehouse,
)


class KitsViewHelpersTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="WH-KIT", code="WHK")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.kit_category = ProductCategory.objects.create(name="Kits")
        self.component_a = Product.objects.create(
            sku="KIT-COMP-A",
            name="Seringue",
            qr_code_image="qr_codes/kit_comp_a.png",
        )
        self.component_b = Product.objects.create(
            sku="KIT-COMP-B",
            name="Compresse",
            qr_code_image="qr_codes/kit_comp_b.png",
        )
        self.lot_a = ProductLot.objects.create(
            product=self.component_a,
            lot_code="LOT-A",
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=10,
            quantity_reserved=0,
            location=self.location,
        )
        self.lot_b = ProductLot.objects.create(
            product=self.component_b,
            lot_code="LOT-B",
            received_on=date(2025, 12, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            quantity_reserved=0,
            location=self.location,
        )
        self.kit = Product.objects.create(
            sku="KIT-PEDIATRIQUE",
            name="Kit Pediatrique",
            category=self.kit_category,
            qr_code_image="qr_codes/kit_pediatrique.png",
        )
        ProductKitItem.objects.create(kit=self.kit, component=self.component_a, quantity=2)
        ProductKitItem.objects.create(kit=self.kit, component=self.component_b, quantity=4)
        for index in range(1, 3):
            carton = Carton.objects.create(
                code=f"KIT-READY-{index}",
                status=CartonStatus.PACKED,
            )
            CartonItem.objects.create(
                carton=carton,
                product_lot=self.lot_a,
                quantity=2,
            )
            CartonItem.objects.create(
                carton=carton,
                product_lot=self.lot_b,
                quantity=4,
            )
        picking_carton = Carton.objects.create(
            code="KIT-PICKING-1",
            status=CartonStatus.PICKING,
        )
        CartonItem.objects.create(
            carton=picking_carton,
            product_lot=self.lot_a,
            quantity=2,
        )
        CartonItem.objects.create(
            carton=picking_carton,
            product_lot=self.lot_b,
            quantity=4,
        )

    def test_build_kits_view_rows_returns_expected_values(self):
        rows = build_kits_view_rows()
        row = next(current for current in rows if current["id"] == self.kit.id)

        self.assertEqual(row["name"], "Kit Pediatrique")
        self.assertEqual(
            row["composition_lines"],
            ["Compresse - 4 unite(s)", "Seringue - 2 unite(s)"],
        )
        self.assertEqual(row["theoretical_stock"], 5)
        self.assertEqual(row["real_stock"], 2)
        self.assertEqual(row["in_preparation_stock"], 1)
        self.assertEqual(row["category"], "KITS")
        self.assertIsNotNone(row["last_modified_at"])
