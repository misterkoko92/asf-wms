from django.test import TestCase

from contacts.models import ContactTag
from wms.import_services import build_contact_tags, build_product_tags
from wms.models import ProductTag


class ImportTagsTests(TestCase):
    def test_build_product_tags_creates_tags(self):
        tags = build_product_tags("alpha|beta")
        self.assertEqual({tag.name for tag in tags}, {"alpha", "beta"})
        self.assertEqual(ProductTag.objects.count(), 2)

    def test_build_contact_tags_creates_tags(self):
        initial_count = ContactTag.objects.count()
        tags = build_contact_tags("gamma,delta")
        self.assertEqual({tag.name for tag in tags}, {"gamma", "delta"})
        self.assertEqual(ContactTag.objects.count(), initial_count + 2)
