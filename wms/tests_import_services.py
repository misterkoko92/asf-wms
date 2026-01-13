from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.import_services import import_contacts, import_products_rows
from wms.models import Product


class ImportContactsTests(TestCase):
    def test_import_contacts_skips_duplicate_addresses(self):
        rows = [
            {
                "contact_type": "organization",
                "name": "Org Alpha",
                "tags": "donateur",
                "address_line1": "1 Rue Exemple",
                "city": "Paris",
                "postal_code": "75001",
                "country": "France",
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 1)
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(ContactAddress.objects.count(), 1)

        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(Contact.objects.count(), 1)
        self.assertEqual(ContactAddress.objects.count(), 1)

    def test_import_contacts_allows_missing_tags_when_existing(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org Beta",
            contact_type=ContactType.ORGANIZATION,
        )
        contact.tags.add(tag)

        rows = [
            {
                "contact_type": "organization",
                "name": "ORG BETA",
                "phone": "0102030405",
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)

        contact.refresh_from_db()
        self.assertEqual(contact.phone, "0102030405")
        self.assertEqual(list(contact.tags.values_list("name", flat=True)), ["donateur"])

    def test_import_contacts_merges_tags_with_warning(self):
        tag = ContactTag.objects.create(name="donateur")
        contact = Contact.objects.create(
            name="Org Gamma",
            contact_type=ContactType.ORGANIZATION,
        )
        contact.tags.add(tag)

        rows = [
            {
                "contact_type": "organization",
                "name": "Org Gamma",
                "tags": "donateur|transporteur",
            }
        ]
        created, updated, errors, warnings = import_contacts(rows)
        self.assertEqual(errors, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        self.assertEqual(len(warnings), 1)

        contact.refresh_from_db()
        tag_names = sorted(contact.tags.values_list("name", flat=True))
        self.assertEqual(tag_names, ["donateur", "transporteur"])


class ImportProductsTests(TestCase):
    def test_import_products_rows_creates_product(self):
        rows = [{"name": "Thermometre", "sku": "TH-001", "brand": "ACME"}]
        created, updated, errors, warnings = import_products_rows(rows, start_index=1)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertEqual(Product.objects.count(), 1)

    def test_import_products_rows_updates_existing_product(self):
        product = Product.objects.create(name="Gants", sku="GNT-1", brand="Old")
        rows = [{"name": "Gants", "sku": "GNT-1", "brand": "New"}]
        decisions = {1: {"action": "update", "product_id": product.id}}
        created, updated, errors, warnings = import_products_rows(
            rows, start_index=1, decisions=decisions
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 1)
        product.refresh_from_db()
        self.assertEqual(product.brand, "New")

    def test_import_products_rows_create_with_duplicate_sku_warns(self):
        Product.objects.create(name="Seringue", sku="SRG-1", brand="ACME")
        rows = [{"name": "Seringue", "sku": "SRG-1", "brand": "ACME"}]
        decisions = {1: {"action": "create"}}
        created, updated, errors, warnings = import_products_rows(
            rows, start_index=1, decisions=decisions
        )
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        self.assertEqual(updated, 0)
        self.assertTrue(warnings)
        self.assertEqual(Product.objects.filter(sku="SRG-1").count(), 1)
