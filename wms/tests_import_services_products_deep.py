from decimal import Decimal
from pathlib import Path
import tempfile
from unittest import mock

from django.test import TestCase

from wms.import_services_products import (
    _apply_quantity,
    attach_photo,
    find_product_matches,
    import_product_row,
    import_products_rows,
    import_products_single,
    resolve_photo_path,
)
from wms.models import (
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductTag,
    Warehouse,
)
from wms.services import StockError


class ImportProductsHelperTests(TestCase):
    def test_find_product_matches_returns_empty_when_no_match(self):
        Product.objects.create(name="Mask", sku="MSK-1", brand="ACME")
        matches, mode = find_product_matches(sku="MSK-2", name="Unknown", brand="ACME")
        self.assertEqual(matches, [])
        self.assertIsNone(mode)

    def test_resolve_photo_path_handles_none_blank_relative_and_absolute(self):
        self.assertIsNone(resolve_photo_path(None, Path("/tmp")))
        self.assertIsNone(resolve_photo_path("   ", Path("/tmp")))
        self.assertIsNone(resolve_photo_path("relative.jpg", None))

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            relative = resolve_photo_path("images/photo.jpg", base_dir)
            self.assertEqual(relative, base_dir / "images/photo.jpg")

            absolute_path = str(base_dir / "absolute.jpg")
            resolved_absolute = resolve_photo_path(absolute_path, None)
            self.assertEqual(resolved_absolute, Path(absolute_path))

    def test_attach_photo_raises_when_file_missing_and_attaches_when_present(self):
        product = Product(name="Photo product")
        with self.assertRaisesMessage(ValueError, "Photo introuvable:"):
            attach_photo(product, Path("/does/not/exist.jpg"))

        with tempfile.TemporaryDirectory() as tmpdir:
            photo_path = Path(tmpdir) / "photo.jpg"
            photo_path.write_bytes(b"fake image bytes")

            attached = attach_photo(product, photo_path)

        self.assertTrue(attached)
        saved_name = Path(product.photo.name).name
        self.assertTrue(saved_name.startswith("photo"))
        self.assertTrue(saved_name.endswith(".jpg"))

    def test_apply_quantity_validates_quantity_location_and_stock_errors(self):
        product = Product.objects.create(name="Qty Product", sku="QTY-1")

        with self.assertRaisesMessage(ValueError, "Quantite invalide."):
            _apply_quantity(product=product, quantity=0, location=None)
        with self.assertRaisesMessage(ValueError, "Emplacement requis pour la quantite."):
            _apply_quantity(product=product, quantity=1, location=None)

        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        with mock.patch(
            "wms.import_services_products.receive_stock",
            side_effect=StockError("stock boom"),
        ):
            with self.assertRaisesMessage(ValueError, "stock boom"):
                _apply_quantity(product=product, quantity=1, location=location)


class ImportProductRowDeepTests(TestCase):
    def test_import_product_row_requires_name(self):
        with self.assertRaisesMessage(ValueError, "Nom produit requis."):
            import_product_row({"sku": "SKU-1"})

    def test_import_product_row_rejects_duplicate_sku_without_existing_product(self):
        Product.objects.create(name="Existing", sku="SKU-EXIST")
        with self.assertRaisesMessage(ValueError, "SKU deja utilise."):
            import_product_row({"name": "New", "sku": "SKU-EXIST"})

    def test_import_product_row_create_sets_optional_fields_tags_and_photo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            photo_path = base_dir / "photo_create.jpg"
            photo_path.write_bytes(b"fake")

            row = {
                "name": "kit sterile",
                "sku": "KIT-001",
                "brand": "acme",
                "ean": "EAN-1",
                "barcode": "BAR-1",
                "color": "Blue",
                "pu_ht": "10.00",
                "tva": "20",
                "warehouse": "W1",
                "zone": "a",
                "aisle": "1",
                "shelf": "2",
                "length_cm": "2",
                "width_cm": "3",
                "height_cm": "4",
                "weight_g": "150",
                "storage_conditions": "dry",
                "perishable": "oui",
                "quarantine_default": "non",
                "notes": "fragile",
                "tags": "urgent|medical",
                "category_l1": "medical",
                "category_l2": "consumables",
                "photo": "photo_create.jpg",
                "quantity": "3",
            }

            product, created, warnings = import_product_row(row, base_dir=base_dir)

        self.assertTrue(created)
        self.assertEqual(warnings, [])
        self.assertEqual(product.name, "Kit Sterile")
        self.assertEqual(product.brand, "ACME")
        self.assertEqual(product.ean, "EAN-1")
        self.assertEqual(product.barcode, "BAR-1")
        self.assertEqual(product.color, "Blue")
        self.assertEqual(product.pu_ht, Decimal("10.00"))
        self.assertEqual(product.tva, Decimal("0.2000"))
        self.assertEqual(product.weight_g, 150)
        self.assertEqual(product.volume_cm3, 24)
        self.assertEqual(product.storage_conditions, "dry")
        self.assertTrue(product.perishable)
        self.assertFalse(product.quarantine_default)
        self.assertEqual(product.notes, "fragile")
        self.assertIn("photo_create", Path(product.photo.name).name)
        self.assertIsNotNone(product.default_location_id)
        self.assertEqual(
            sorted(product.tags.values_list("name", flat=True)),
            ["medical", "urgent"],
        )
        self.assertEqual(ProductLot.objects.filter(product=product).count(), 1)

    def test_import_product_row_update_sets_optional_fields_tags_and_photo(self):
        old_category = ProductCategory.objects.create(name="Old")
        product = Product.objects.create(
            name="Old Name",
            sku="UPD-1",
            brand="OLD",
            category=old_category,
            notes="old notes",
        )
        old_tag = ProductTag.objects.create(name="legacy")
        product.tags.add(old_tag)

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            photo_path = base_dir / "photo_update.jpg"
            photo_path.write_bytes(b"fake")

            row = {
                "name": "new name",
                "ean": "EAN-UPD",
                "barcode": "BAR-UPD",
                "brand": "newbrand",
                "color": "Green",
                "pu_ht": "12.50",
                "tva": "0.2",
                "warehouse": "W2",
                "zone": "z",
                "aisle": "2",
                "shelf": "3",
                "length_cm": "5",
                "width_cm": "6",
                "height_cm": "7",
                "weight_g": "300",
                "storage_conditions": "cold",
                "perishable": "yes",
                "quarantine_default": "no",
                "notes": "updated notes",
                "tags": "new1|new2",
                "category_l1": "new-root",
                "category_l2": "child",
                "photo": "photo_update.jpg",
                "quantity": "2",
            }

            updated, was_created, warnings = import_product_row(
                row,
                existing_product=product,
                base_dir=base_dir,
            )

        self.assertFalse(was_created)
        self.assertEqual(warnings, [])
        self.assertEqual(updated.id, product.id)
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.brand, "NEWBRAND")
        self.assertEqual(updated.ean, "EAN-UPD")
        self.assertEqual(updated.barcode, "BAR-UPD")
        self.assertEqual(updated.color, "Green")
        self.assertEqual(updated.pu_ht, Decimal("12.50"))
        self.assertEqual(updated.tva, Decimal("0.2000"))
        self.assertEqual(updated.weight_g, 300)
        self.assertEqual(updated.volume_cm3, 210)
        self.assertEqual(updated.storage_conditions, "cold")
        self.assertTrue(updated.perishable)
        self.assertFalse(updated.quarantine_default)
        self.assertEqual(updated.notes, "updated notes")
        self.assertIn("photo_update", Path(updated.photo.name).name)
        self.assertIsNotNone(updated.default_location_id)
        self.assertEqual(
            sorted(updated.tags.values_list("name", flat=True)),
            ["new1", "new2"],
        )
        self.assertEqual(ProductLot.objects.filter(product=updated).count(), 1)


class ImportProductsRowsDeepTests(TestCase):
    def test_import_products_rows_skips_empty_row_and_reports_missing_update_target(self):
        rows = [{}, {"name": "Some product", "sku": "S-1"}]
        decisions = {3: {"action": "update", "product_id": 999999}}

        created, updated, errors, warnings = import_products_rows(rows, decisions=decisions)

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 3: produit cible introuvable."])

    def test_import_products_rows_collects_row_value_errors_and_continues(self):
        rows = [
            {"sku": "BAD-1"},  # missing name -> ValueError
            {"name": "Good Product", "sku": "GOOD-1"},
        ]

        created, updated, errors, warnings = import_products_rows(rows)

        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(errors, ["Ligne 2: Nom produit requis."])
        self.assertTrue(Product.objects.filter(sku="GOOD-1").exists())

    def test_import_products_single_delegates_to_import_product_row(self):
        product = import_products_single({"name": "Single Product", "sku": "SINGLE-1"})
        self.assertEqual(product.name, "Single Product")
        self.assertEqual(product.sku, "SINGLE-1")
