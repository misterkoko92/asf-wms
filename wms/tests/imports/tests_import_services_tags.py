from django.test import TestCase

from wms.import_services import build_product_tags
from wms.models import ProductTag


class ImportTagsTests(TestCase):
    def test_build_product_tags_creates_tags(self):
        tags = build_product_tags("alpha|beta")
        self.assertEqual({tag.name for tag in tags}, {"alpha", "beta"})
        self.assertEqual(ProductTag.objects.count(), 2)
