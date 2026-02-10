from django.test import TestCase

from wms.import_services import import_categories
from wms.import_services_categories import build_category_path
from wms.models import ProductCategory


class ImportCategoriesTests(TestCase):
    def test_build_category_path_skips_empty_parts(self):
        leaf = build_category_path(["medical", "", None, "epi"])

        self.assertEqual(leaf.name, "EPI")
        self.assertEqual(leaf.parent.name, "MEDICAL")
        self.assertEqual(ProductCategory.objects.count(), 2)

    def test_import_categories_path_creates_hierarchy(self):
        rows = [{"path": "mm > epi / gants"}]
        created, updated, errors = import_categories(rows)
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        root = ProductCategory.objects.get(name="MM", parent=None)
        child = ProductCategory.objects.get(name="EPI", parent=root)
        leaf = ProductCategory.objects.get(name="Gants", parent=child)
        self.assertIsNotNone(leaf)

    def test_import_categories_name_parent(self):
        rows = [{"name": "thermometre", "parent": "medical"}]
        created, updated, errors = import_categories(rows)
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        root = ProductCategory.objects.get(name="MEDICAL", parent=None)
        child = ProductCategory.objects.get(name="Thermometre", parent=root)
        self.assertIsNotNone(child)

    def test_import_categories_skips_empty_row(self):
        created, updated, errors = import_categories([{"path": "   ", "name": ""}])

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, [])

    def test_import_categories_reports_empty_path(self):
        created, updated, errors = import_categories([{"path": " // > / "}])

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, ["Ligne 2: Chemin categorie vide."])

    def test_import_categories_requires_name_when_path_missing(self):
        created, updated, errors = import_categories([{"parent": "medical"}])

        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(errors, ["Ligne 2: Nom categorie requis."])
