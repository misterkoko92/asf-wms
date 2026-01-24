from django.test import TestCase

from wms.import_services import import_categories
from wms.models import ProductCategory


class ImportCategoriesTests(TestCase):
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
