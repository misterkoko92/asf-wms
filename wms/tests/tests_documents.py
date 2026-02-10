from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from contacts.models import Contact, ContactType
from wms.documents import (
    _format_contact_address,
    _resolve_contact,
    build_contact_info,
    build_shipment_type_labels,
)
from wms.models import (
    Carton,
    CartonItem,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    Shipment,
    Warehouse,
)


class DocumentsHelpersTests(TestCase):
    def test_build_shipment_type_labels_uses_root_categories(self):
        root = ProductCategory.objects.create(name="MEDICAL")
        child = ProductCategory.objects.create(name="Gants", parent=root)
        warehouse = Warehouse.objects.create(name="WH-DOC")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(name="Produit Doc", category=child)
        lot = ProductLot.objects.create(
            product=product,
            quantity_on_hand=1,
            location=location,
        )
        shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        carton = Carton.objects.create(code="C-DOC-1", shipment=shipment)
        CartonItem.objects.create(carton=carton, product_lot=lot, quantity=1)

        labels = build_shipment_type_labels(shipment)

        self.assertEqual(labels, "MEDICAL")

    def test_resolve_contact_handles_empty_and_fallback_lookup(self):
        self.assertIsNone(_resolve_contact(("donateur",), ""))

        expected = Contact.objects.create(
            name="Fallback Contact",
            contact_type=ContactType.ORGANIZATION,
        )
        with mock.patch("wms.documents.contacts_with_tags", return_value=Contact.objects.none()):
            resolved = _resolve_contact(("donateur",), "Fallback Contact")

        self.assertEqual(resolved.id, expected.id)


class DocumentsFormattingTests(SimpleTestCase):
    def test_format_contact_address_handles_none_and_optional_lines(self):
        self.assertEqual(_format_contact_address(None), "")

        address = SimpleNamespace(
            address_line1="1 Rue Test",
            address_line2="Batiment A",
            postal_code="75001",
            city="Paris",
            region="Ile-de-France",
            country="France",
        )
        formatted = _format_contact_address(address)

        self.assertIn("Batiment A", formatted)
        self.assertIn("Ile-de-France", formatted)

    def test_build_contact_info_returns_fallback_when_contact_missing(self):
        with mock.patch("wms.documents._resolve_contact", return_value=None):
            info = build_contact_info(("tag",), "Fallback Name")

        self.assertEqual(info["name"], "Fallback Name")
        self.assertEqual(info["company"], "Fallback Name")
        self.assertEqual(info["address"], "")

    def test_build_contact_info_uses_address_manager_when_no_effective_method(self):
        address = SimpleNamespace(
            address_line1="1 Rue Test",
            address_line2="",
            postal_code="75001",
            city="Paris",
            region="IDF",
            country="France",
            phone="0102030405",
            email="contact@example.com",
        )
        addresses = SimpleNamespace(
            filter=lambda **kwargs: SimpleNamespace(first=lambda: address),
            first=lambda: address,
        )
        contact = SimpleNamespace(
            name="Org Contact",
            contact_type=ContactType.ORGANIZATION,
            notes="Primary Person",
            phone="",
            email="",
            addresses=addresses,
        )

        with mock.patch("wms.documents._resolve_contact", return_value=contact):
            info = build_contact_info(("tag",), "Org Contact")

        self.assertEqual(info["company"], "Org Contact")
        self.assertEqual(info["person"], "Primary Person")
        self.assertEqual(info["phone"], "0102030405")
        self.assertEqual(info["email"], "contact@example.com")
