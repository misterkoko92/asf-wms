from types import SimpleNamespace

from django.test import SimpleTestCase

from wms.product_display import build_product_display, category_levels


class ProductDisplayTests(SimpleTestCase):
    def test_category_levels_handles_none_truncation_and_padding(self):
        self.assertEqual(category_levels(None), ["", "", "", ""])

        root = SimpleNamespace(name="Root", parent=None)
        child = SimpleNamespace(name="Child", parent=root)
        leaf = SimpleNamespace(name="Leaf", parent=child)
        self.assertEqual(category_levels(leaf), ["Root", "Child", "Leaf", ""])
        self.assertEqual(category_levels(leaf, max_levels=2), ["Root", "Child"])

    def test_build_product_display_with_location_and_tags(self):
        category = SimpleNamespace(name="Cat2", parent=SimpleNamespace(name="Cat1", parent=None))
        location = SimpleNamespace(
            warehouse=SimpleNamespace(name="WH-A"),
            zone="Z1",
            aisle="A1",
            shelf="S1",
        )
        tags = SimpleNamespace(values_list=lambda *args, **kwargs: ["Urgent", "Medical"])
        product = SimpleNamespace(
            id=10,
            sku="SKU-10",
            name="Mask",
            brand="BrandX",
            color="Blue",
            category=category,
            barcode="123",
            ean="456",
            tags=tags,
            pu_ht="9.99",
            tva="20",
            length_cm=10,
            width_cm=20,
            height_cm=30,
            weight_g=500,
            volume_cm3=6000,
            storage_conditions="Dry",
            perishable=True,
            quarantine_default=False,
            notes="note",
            default_location=location,
        )

        data = build_product_display(product)

        self.assertEqual(data["id"], 10)
        self.assertEqual(data["category_l1"], "Cat1")
        self.assertEqual(data["category_l2"], "Cat2")
        self.assertEqual(data["tags"], "Urgent | Medical")
        self.assertEqual(data["perishable"], "Oui")
        self.assertEqual(data["quarantine_default"], "Non")
        self.assertEqual(data["warehouse"], "WH-A")
        self.assertEqual(data["zone"], "Z1")
        self.assertEqual(data["aisle"], "A1")
        self.assertEqual(data["shelf"], "S1")

    def test_build_product_display_without_location_or_optional_values(self):
        tags = SimpleNamespace(values_list=lambda *args, **kwargs: [])
        product = SimpleNamespace(
            id=20,
            sku="SKU-20",
            name="Gloves",
            brand="",
            color="",
            category=None,
            barcode="",
            ean="",
            tags=tags,
            pu_ht=None,
            tva=None,
            length_cm=None,
            width_cm=None,
            height_cm=None,
            weight_g=None,
            volume_cm3=None,
            storage_conditions="",
            perishable=False,
            quarantine_default=True,
            notes=None,
            default_location=None,
        )

        data = build_product_display(product)

        self.assertEqual(data["category_l1"], "")
        self.assertEqual(data["tags"], "")
        self.assertEqual(data["pu_ht"], "")
        self.assertEqual(data["tva"], "")
        self.assertEqual(data["perishable"], "Non")
        self.assertEqual(data["quarantine_default"], "Oui")
        self.assertEqual(data["warehouse"], "")
        self.assertEqual(data["zone"], "")
        self.assertEqual(data["aisle"], "")
        self.assertEqual(data["shelf"], "")
