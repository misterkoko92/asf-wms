import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from wms.management.commands import import_products
from wms.models import Location, Product, ProductCategory, ProductTag, RackColor, Warehouse


class ImportProductsHelpersTests(TestCase):
    def test_parse_wrappers_raise_command_error_on_invalid_values(self):
        with self.assertRaisesMessage(CommandError, "Invalid decimal value"):
            import_products.parse_decimal("abc")
        with self.assertRaisesMessage(CommandError, "Invalid decimal value"):
            import_products.parse_int("abc")
        with self.assertRaisesMessage(CommandError, "Invalid boolean value"):
            import_products.parse_bool("maybe")

    def test_resolve_photo_path_variants(self):
        base_dir = Path("/tmp/products-import")
        absolute = Path("/tmp/photo.png")

        self.assertIsNone(import_products.resolve_photo_path(None, base_dir))
        self.assertIsNone(import_products.resolve_photo_path("   ", base_dir))
        self.assertEqual(
            import_products.resolve_photo_path("photo.png", base_dir),
            base_dir / "photo.png",
        )
        self.assertEqual(
            import_products.resolve_photo_path(str(absolute), base_dir),
            absolute,
        )

    def test_attach_photo_behaviors(self):
        product = mock.Mock()
        product.photo.save = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            existing = tmp_path / "photo.jpg"
            existing.write_bytes(b"binary-data")

            self.assertFalse(import_products.attach_photo(product, None, dry_run=False))
            self.assertFalse(import_products.attach_photo(product, existing, dry_run=True))
            self.assertTrue(import_products.attach_photo(product, existing, dry_run=False))

            missing = tmp_path / "missing.jpg"
            with self.assertRaisesMessage(CommandError, "Photo not found"):
                import_products.attach_photo(product, missing, dry_run=False)

        product.photo.save.assert_called_once()
        _, kwargs = product.photo.save.call_args
        self.assertEqual(kwargs["save"], False)

    def test_apply_quantity_branches(self):
        product = SimpleNamespace(default_location=None)
        import_products.apply_quantity(product, None, None, dry_run=False, row_number=4)

        with self.assertRaisesMessage(CommandError, "invalid quantity value"):
            import_products.apply_quantity(
                product,
                0,
                None,
                dry_run=False,
                row_number=5,
            )

        with self.assertRaisesMessage(CommandError, "location required"):
            import_products.apply_quantity(
                product,
                2,
                None,
                dry_run=False,
                row_number=6,
            )

        with mock.patch(
            "wms.management.commands.import_products.receive_stock"
        ) as receive_stock_mock:
            import_products.apply_quantity(
                product,
                2,
                "LOC",
                dry_run=True,
                row_number=7,
            )
        receive_stock_mock.assert_not_called()

        default_product = SimpleNamespace(default_location="DEFAULT")
        with mock.patch(
            "wms.management.commands.import_products.receive_stock"
        ) as receive_stock_mock:
            import_products.apply_quantity(
                default_product,
                3,
                None,
                dry_run=False,
                row_number=8,
            )
        receive_stock_mock.assert_called_once_with(
            user=None,
            product=default_product,
            quantity=3,
            location="DEFAULT",
        )

        with mock.patch(
            "wms.management.commands.import_products.receive_stock",
            side_effect=import_products.StockError("boom"),
        ):
            with self.assertRaisesMessage(CommandError, "Row 9: boom"):
                import_products.apply_quantity(
                    default_product,
                    3,
                    None,
                    dry_run=False,
                    row_number=9,
                )

    def test_build_category_path_build_tags_location_and_volume(self):
        parent = import_products.build_category_path(["Medical", "", "EPI"])
        self.assertIsNotNone(parent)
        self.assertEqual(parent.name, "EPI")
        self.assertEqual(parent.parent.name, "MEDICAL")

        tags, provided = import_products.build_tags(None)
        self.assertEqual(tags, [])
        self.assertFalse(provided)

        tags, provided = import_products.build_tags("cold| |urgent")
        self.assertTrue(provided)
        self.assertEqual({tag.name for tag in tags}, {"cold", "urgent"})

        stderr = StringIO()
        self.assertIsNone(
            import_products.get_or_create_location(None, None, None, None, 1, stderr)
        )
        self.assertIsNone(
            import_products.get_or_create_location("W1", "A", "", "C", 2, stderr)
        )
        self.assertIn("Row 2: incomplete location", stderr.getvalue())

        location = import_products.get_or_create_location("W1", "A", "B", "C", 3, stderr)
        self.assertIsNotNone(location)
        self.assertEqual(
            (location.warehouse.name, location.zone, location.aisle, location.shelf),
            ("W1", "A", "B", "C"),
        )

        self.assertIsNone(import_products.compute_volume(None, Decimal("2"), Decimal("3")))
        self.assertEqual(
            import_products.compute_volume(
                Decimal("2.0"),
                Decimal("3.0"),
                Decimal("4.0"),
            ),
            24,
        )

    def test_iter_csv_rows_normalizes_headers(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "products.csv"
            path.write_text("SKU;Nom Produit\nABC-1;Produit test\n", encoding="utf-8-sig")

            rows = list(import_products.iter_csv_rows(path))

        self.assertEqual(rows, [{"sku": "ABC-1", "nom_produit": "Produit test"}])

    def test_iter_excel_rows_branches(self):
        with mock.patch.object(import_products, "xlrd", None):
            with self.assertRaisesMessage(CommandError, "xlrd is required"):
                list(import_products.iter_excel_rows(Path("input.xls")))

        empty_sheet = mock.Mock()
        empty_sheet.nrows = 0
        xlrd_module = mock.Mock()
        xlrd_module.open_workbook.return_value.sheet_by_index.return_value = empty_sheet
        with mock.patch.object(import_products, "xlrd", xlrd_module):
            with self.assertRaisesMessage(CommandError, "Excel file is empty"):
                list(import_products.iter_excel_rows(Path("input.xls")))

        sheet = mock.Mock()
        sheet.nrows = 2
        sheet.row.return_value = [
            SimpleNamespace(value="SKU"),
            SimpleNamespace(value="Name"),
            SimpleNamespace(value=""),
        ]
        sheet.cell_value.side_effect = lambda row, col: {
            (1, 0): "A-1",
            (1, 1): "Gants",
            (1, 2): "ignored",
        }[(row, col)]
        xlrd_module = mock.Mock()
        xlrd_module.open_workbook.return_value.sheet_by_index.return_value = sheet
        with mock.patch.object(import_products, "xlrd", xlrd_module):
            rows = list(import_products.iter_excel_rows(Path("ok.xls")))
        self.assertEqual(rows, [{"sku": "A-1", "name": "Gants"}])

        with mock.patch.object(import_products, "load_workbook", None):
            with self.assertRaisesMessage(CommandError, "openpyxl is required"):
                list(import_products.iter_excel_rows(Path("input.xlsx")))

        workbook = mock.Mock()
        workbook.active.iter_rows.return_value = iter(())
        with mock.patch.object(import_products, "load_workbook", return_value=workbook):
            with self.assertRaisesMessage(CommandError, "Excel file is empty"):
                list(import_products.iter_excel_rows(Path("empty.xlsx")))

        workbook = mock.Mock()
        workbook.active.iter_rows.return_value = iter(
            [
                ("SKU", "Name", ""),
                ("B-1", "Produit A", "ignored"),
                ("B-2", "Produit B", "ignored"),
            ]
        )
        with mock.patch.object(import_products, "load_workbook", return_value=workbook):
            rows = list(import_products.iter_excel_rows(Path("ok.xlsx")))
        self.assertEqual(
            rows,
            [
                {"sku": "B-1", "name": "Produit A"},
                {"sku": "B-2", "name": "Produit B"},
            ],
        )


class ImportProductsCommandTests(TestCase):
    def _make_input_file(self, suffix=".csv"):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = Path(tmp_dir.name) / f"import{suffix}"
        path.write_text("placeholder", encoding="utf-8")
        return path

    def test_handle_raises_on_missing_file(self):
        with self.assertRaisesMessage(CommandError, "File not found"):
            call_command("import_products", "/tmp/does-not-exist.csv")

    def test_handle_creates_skips_and_collects_row_errors(self):
        Product.objects.create(name="Existing Product", sku="EX-1", brand="ACME")
        path = self._make_input_file(".csv")
        rows = [
            {"sku": "EX-1", "name": "Should Skip"},
            {"sku": "ERR-1"},
            {
                "sku": "NEW-1",
                "name": "sterile gloves",
                "barcode": "BAR-NEW",
                "brand": "acme",
                "color": "white",
                "category_l1": "medical",
                "category_l2": "epi",
                "tags": "cold|urgent",
                "warehouse": "W1",
                "zone": "a",
                "aisle": "b",
                "shelf": "c",
                "rack_color": "blue",
                "length_cm": "2",
                "width_cm": "3",
                "height_cm": "4",
                "weight_g": "50",
                "storage_conditions": "cool",
                "perishable": "yes",
                "quarantine_default": "no",
                "notes": "new item",
                "quantity": "2",
            },
        ]
        out = StringIO()
        err = StringIO()
        with mock.patch(
            "wms.management.commands.import_products.iter_csv_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_products.apply_quantity"
        ) as apply_quantity_mock, mock.patch(
            "wms.management.commands.import_products.attach_photo",
            return_value=False,
        ):
            call_command(
                "import_products",
                str(path),
                "--skip-errors",
                stdout=out,
                stderr=err,
            )

        product = Product.objects.get(sku="NEW-1")
        self.assertEqual(product.name, "Sterile Gloves")
        self.assertEqual(product.barcode, "BAR-NEW")
        self.assertEqual(product.brand, "ACME")
        self.assertEqual(product.color, "white")
        self.assertEqual(product.weight_g, 50)
        self.assertEqual(product.volume_cm3, 24)
        self.assertEqual(product.storage_conditions, "cool")
        self.assertTrue(product.perishable)
        self.assertFalse(product.quarantine_default)
        self.assertEqual(product.notes, "new item")
        self.assertEqual({tag.name for tag in product.tags.all()}, {"cold", "urgent"})
        self.assertEqual(ProductCategory.objects.filter(name="MEDICAL").count(), 1)
        self.assertEqual(RackColor.objects.filter(warehouse__name="W1", zone="A").count(), 1)
        self.assertIn("created=1, updated=0, skipped=1, errors=1", out.getvalue())
        self.assertIn("Row 3: Missing required field: name", err.getvalue())
        apply_quantity_mock.assert_called_once()

    def test_handle_updates_existing_products(self):
        product = Product.objects.create(name="Old name", sku="UPD-1", brand="OLD")
        old_tag = ProductTag.objects.create(name="old")
        product.tags.add(old_tag)

        path = self._make_input_file(".csv")
        rows = [
            {
                "sku": "UPD-1",
                "name": "new updated product",
                "barcode": "BAR-123",
                "brand": "newbrand",
                "color": "green",
                "category_l1": "new-root",
                "warehouse": "W2",
                "zone": "z",
                "aisle": "1",
                "shelf": "2",
                "tags": "fresh",
                "length_cm": "10",
                "width_cm": "11",
                "height_cm": "12",
                "weight_g": "90",
                "volume_cm3": "120",
                "storage_conditions": "frais",
                "perishable": "yes",
                "quarantine_default": "yes",
                "notes": "updated",
                "photo": "fake.jpg",
                "quantity": "4",
            }
        ]
        out = StringIO()
        with mock.patch(
            "wms.management.commands.import_products.iter_csv_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_products.apply_quantity"
        ) as apply_quantity_mock, mock.patch(
            "wms.management.commands.import_products.attach_photo",
            return_value=True,
        ):
            call_command("import_products", str(path), "--update", stdout=out)

        product.refresh_from_db()
        self.assertEqual(product.name, "New Updated Product")
        self.assertEqual(product.barcode, "BAR-123")
        self.assertEqual(product.brand, "NEWBRAND")
        self.assertEqual(product.color, "green")
        self.assertEqual(product.category.name, "NEW-ROOT")
        self.assertEqual(product.length_cm, 10)
        self.assertEqual(product.width_cm, 11)
        self.assertEqual(product.height_cm, 12)
        self.assertEqual(product.weight_g, 90)
        self.assertEqual(product.volume_cm3, 120)
        self.assertEqual(product.storage_conditions, "frais")
        self.assertTrue(product.perishable)
        self.assertTrue(product.quarantine_default)
        self.assertEqual(product.notes, "updated")
        self.assertIsNotNone(product.default_location)
        self.assertEqual({tag.name for tag in product.tags.all()}, {"fresh"})
        self.assertIn("created=0, updated=1, skipped=0, errors=0", out.getvalue())
        apply_quantity_mock.assert_called_once()

    def test_handle_update_requires_sku(self):
        path = self._make_input_file(".csv")
        rows = [{"name": "No SKU"}]
        with mock.patch(
            "wms.management.commands.import_products.iter_csv_rows",
            return_value=iter(rows),
        ):
            with self.assertRaisesMessage(
                CommandError,
                "Missing required field for update: sku",
            ):
                call_command("import_products", str(path), "--update")

    def test_handle_raises_row_error_without_skip_errors(self):
        path = self._make_input_file(".csv")
        rows = [{"sku": "ERR-2"}]
        with mock.patch(
            "wms.management.commands.import_products.iter_csv_rows",
            return_value=iter(rows),
        ):
            with self.assertRaisesMessage(CommandError, "Missing required field: name"):
                call_command("import_products", str(path))

    def test_handle_dry_run_rolls_back_and_marks_summary(self):
        path = self._make_input_file(".csv")
        rows = [{"sku": "DRY-1", "name": "Dry product"}]
        out = StringIO()
        with mock.patch(
            "wms.management.commands.import_products.iter_csv_rows",
            return_value=iter(rows),
        ), mock.patch(
            "wms.management.commands.import_products.apply_quantity"
        ), mock.patch(
            "wms.management.commands.import_products.attach_photo",
            return_value=False,
        ):
            call_command("import_products", str(path), "--dry-run", stdout=out)
        self.assertFalse(Product.objects.filter(sku="DRY-1").exists())
        self.assertIn("(dry-run)", out.getvalue())

    def test_handle_uses_excel_iterator_for_excel_files(self):
        path = self._make_input_file(".xlsx")
        out = StringIO()
        with mock.patch(
            "wms.management.commands.import_products.iter_excel_rows",
            return_value=iter(()),
        ) as iter_excel_mock:
            call_command("import_products", str(path), stdout=out)
        iter_excel_mock.assert_called_once_with(path)
        self.assertIn("created=0, updated=0, skipped=0, errors=0", out.getvalue())
