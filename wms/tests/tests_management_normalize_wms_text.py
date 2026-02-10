from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from wms.models import Location, Product, ProductCategory, RackColor, Warehouse
from wms.text_utils import normalize_category_name, normalize_title, normalize_upper


class NormalizeWmsTextCommandTests(TestCase):
    def test_command_normalizes_entities_and_reports_counts(self):
        warehouse = Warehouse.objects.create(name="Main")

        product = Product.objects.create(name="Produit test", brand="ASF")
        Product.objects.filter(pk=product.pk).update(
            name="masque chirurgical", brand="acme"
        )

        category = ProductCategory.objects.create(name="Medical")
        ProductCategory.objects.filter(pk=category.pk).update(name="medical")

        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="B",
            shelf="C",
        )
        Location.objects.filter(pk=location.pk).update(zone="a", aisle="b", shelf="c")

        rack = RackColor.objects.create(warehouse=warehouse, zone="A", color="Blue")
        RackColor.objects.filter(pk=rack.pk).update(zone="a")

        out = StringIO()
        call_command("normalize_wms_text", stdout=out)

        product.refresh_from_db()
        category.refresh_from_db()
        location.refresh_from_db()
        rack.refresh_from_db()

        self.assertEqual(product.name, normalize_title("masque chirurgical"))
        self.assertEqual(product.brand, normalize_upper("acme"))
        self.assertEqual(category.name, normalize_category_name("medical", is_root=True))
        self.assertEqual(location.zone, normalize_upper("a"))
        self.assertEqual(location.aisle, normalize_upper("b"))
        self.assertEqual(location.shelf, normalize_upper("c"))
        self.assertEqual(rack.zone, normalize_upper("a"))

        self.assertIn(
            "products=1, categories=1, locations=1, rack_colors=1",
            out.getvalue(),
        )

    def test_command_skips_empty_fields_and_reports_zero_updates(self):
        warehouse = Warehouse.objects.create(name="Secondary")

        product = Product.objects.create(name="Already Normalized", brand="ACME")
        Product.objects.filter(pk=product.pk).update(name="", brand="")

        category = ProductCategory.objects.create(name="Root")
        ProductCategory.objects.filter(pk=category.pk).update(name="")

        location = Location.objects.create(
            warehouse=warehouse,
            zone="Z",
            aisle="A",
            shelf="1",
        )
        Location.objects.filter(pk=location.pk).update(zone="", aisle="", shelf="")

        rack = RackColor.objects.create(warehouse=warehouse, zone="X", color="Red")
        RackColor.objects.filter(pk=rack.pk).update(zone="")

        out = StringIO()
        call_command("normalize_wms_text", stdout=out)

        product.refresh_from_db()
        category.refresh_from_db()
        location.refresh_from_db()
        rack.refresh_from_db()

        self.assertEqual(product.name, "")
        self.assertEqual(product.brand, "")
        self.assertEqual(category.name, "")
        self.assertEqual(location.zone, "")
        self.assertEqual(location.aisle, "")
        self.assertEqual(location.shelf, "")
        self.assertEqual(rack.zone, "")
        self.assertIn(
            "products=0, categories=0, locations=0, rack_colors=0",
            out.getvalue(),
        )
