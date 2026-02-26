from django.test import TestCase

from django.contrib.auth import get_user_model
from django.utils import timezone

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.import_services import (
    apply_pallet_listing_import,
    import_contacts,
    import_products_rows,
    resolve_listing_location,
)
from wms.models import Location, Product, ProductLot, ReceiptLine, Warehouse


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
        self.assertEqual(product.brand, "NEW")

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

    def test_import_products_rows_collects_distinct_product_stats(self):
        product = Product.objects.create(name="Gants", sku="GNT-STATS-1", brand="OLD")
        rows = [
            {"name": "Gants", "sku": "GNT-STATS-1", "brand": "NEW"},
            {"name": "Gants", "sku": "GNT-STATS-1", "brand": "NEWER"},
        ]
        decisions = {
            1: {"action": "update", "product_id": product.id},
            2: {"action": "update", "product_id": product.id},
        }
        created, updated, errors, warnings, stats = import_products_rows(
            rows,
            start_index=1,
            decisions=decisions,
            collect_stats=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 2)
        self.assertEqual(stats, {"distinct_products": 1, "temp_location_rows": 0})


class ListingImportTests(TestCase):
    def test_apply_pallet_listing_import_creates_receipt_line(self):
        user = get_user_model().objects.create_user(
            username="tester",
            password="pass",
        )
        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(
            warehouse=warehouse, zone="A", aisle="1", shelf="1"
        )
        product = Product.objects.create(
            name="Gants",
            sku="GNT-1",
            brand="ACME",
            default_location=location,
        )
        donor = Contact.objects.create(
            name="Donateur",
            contact_type=ContactType.ORGANIZATION,
        )
        carrier = Contact.objects.create(
            name="Transporteur",
            contact_type=ContactType.ORGANIZATION,
        )

        row_payloads = [
            {
                "apply": True,
                "row_index": 2,
                "selection": f"product:{product.id}",
                "override_code": "",
                "row_data": {"quantity": "3"},
            }
        ]
        created, skipped, errors, receipt = apply_pallet_listing_import(
            row_payloads,
            user=user,
            warehouse=warehouse,
            receipt_meta={
                "received_on": timezone.localdate(),
                "pallet_count": 1,
                "source_contact_id": donor.id,
                "carrier_contact_id": carrier.id,
                "transport_request_date": "",
            },
        )

        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertIsNotNone(receipt)
        self.assertEqual(ReceiptLine.objects.count(), 1)
        self.assertEqual(ProductLot.objects.count(), 1)

    def test_resolve_listing_location_normalizes_fields(self):
        warehouse = Warehouse.objects.create(name="Main")
        row = {"warehouse": "Main", "zone": "a", "aisle": "b", "shelf": "c"}
        location = resolve_listing_location(row, warehouse)
        self.assertIsNotNone(location)
        self.assertEqual(location.zone, "A")
        self.assertEqual(location.aisle, "B")
        self.assertEqual(location.shelf, "C")
