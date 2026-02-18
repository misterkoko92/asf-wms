from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactTag, ContactType
from wms.models import Destination, Product
from wms.shipment_helpers import (
    build_destination_label,
    build_shipment_contact_payload,
    parse_shipment_lines,
)


class ShipmentHelpersTests(TestCase):
    def test_build_destination_label_returns_empty_for_missing_destination(self):
        self.assertEqual(build_destination_label(None), "")

    def test_build_destination_label_uses_destination_string(self):
        correspondent = Contact.objects.create(name="Correspondent")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=correspondent,
        )
        self.assertEqual(build_destination_label(destination), str(destination))

    def test_build_shipment_contact_payload_collects_destination_scoped_contacts(self):
        correspondent = Contact.objects.create(name="Corr A")
        destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYS",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper.destinations.add(destination)
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper.tags.add(shipper_tag)
        recipient = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient.destinations.add(destination)
        ContactAddress.objects.create(
            contact=recipient,
            address_line1="1 Rue Test",
            city="Lyon",
            country="France",
            is_default=True,
        )
        ContactAddress.objects.create(
            contact=recipient,
            address_line1="2 Main St",
            city="London",
            country="UK",
            is_default=False,
        )
        recipient_tag = ContactTag.objects.create(name="destinataire")
        recipient.tags.add(recipient_tag)

        corr_contact = Contact.objects.create(
            name="Corr Contact",
            is_active=True,
        )
        corr_contact.destinations.add(destination)
        correspondent_tag = ContactTag.objects.create(name="correspondant")
        corr_contact.tags.add(correspondent_tag)

        (
            destinations_json,
            shippers_json,
            recipients_json,
            correspondents_json,
        ) = build_shipment_contact_payload()

        self.assertEqual(
            destinations_json,
            [
                {
                    "id": destination.id,
                    "country": "France",
                    "correspondent_contact_id": correspondent.id,
                }
            ],
        )
        self.assertEqual(
            shippers_json,
            [
                {
                    "id": shipper.id,
                    "name": "Shipper Org",
                    "destination_id": destination.id,
                    "destination_ids": [destination.id],
                }
            ],
        )
        self.assertEqual(len(recipients_json), 1)
        self.assertEqual(recipients_json[0]["id"], recipient.id)
        self.assertEqual(recipients_json[0]["name"], "Recipient Org")
        self.assertEqual(recipients_json[0]["countries"], ["France", "UK"])
        self.assertEqual(recipients_json[0]["destination_id"], destination.id)
        self.assertEqual(recipients_json[0]["destination_ids"], [destination.id])
        self.assertEqual(recipients_json[0]["linked_shipper_ids"], [])
        self.assertEqual(
            correspondents_json,
            [
                {
                    "id": corr_contact.id,
                    "name": "Corr Contact",
                    "destination_id": destination.id,
                    "destination_ids": [destination.id],
                }
            ],
        )

    def test_parse_shipment_lines_collects_all_error_branches(self):
        product = Product.objects.create(
            sku="SHIP-001",
            name="Shipment Product",
            qr_code_image="qr_codes/test.png",
        )
        data = {
            "line_1_carton_id": "1",
            "line_1_product_code": product.sku,
            "line_1_quantity": "1",
            "line_2_carton_id": "2",
            "line_2_product_code": "",
            "line_2_quantity": "",
            "line_3_carton_id": "",
            "line_3_product_code": "",
            "line_3_quantity": "1",
            "line_4_carton_id": "",
            "line_4_product_code": product.sku,
            "line_4_quantity": "",
            "line_5_carton_id": "",
            "line_5_product_code": product.sku,
            "line_5_quantity": "0",
            "line_6_carton_id": "",
            "line_6_product_code": "UNKNOWN",
            "line_6_quantity": "1",
            "line_7_carton_id": "",
            "line_7_product_code": "",
            "line_7_quantity": "",
        }

        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=7,
            data=data,
            allowed_carton_ids={"1"},
        )

        self.assertEqual(len(line_values), 7)
        self.assertEqual(line_items, [])
        self.assertEqual(
            line_errors,
            {
                "1": ["Choisissez un carton OU créez un colis depuis un produit."],
                "2": ["Carton indisponible."],
                "3": ["Produit requis."],
                "4": ["Quantité requise."],
                "5": ["Quantité invalide."],
                "6": ["Produit introuvable."],
                "7": ["Renseignez un carton ou un produit."],
            },
        )

    def test_parse_shipment_lines_accepts_valid_carton_and_product_lines(self):
        product = Product.objects.create(
            sku="SHIP-VALID",
            name="Shipment Valid Product",
            qr_code_image="qr_codes/test.png",
        )
        data = {
            "line_1_carton_id": "10",
            "line_1_product_code": "",
            "line_1_quantity": "",
            "line_2_carton_id": "",
            "line_2_product_code": "SHIP-VALID",
            "line_2_quantity": "3",
        }

        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=2,
            data=data,
            allowed_carton_ids={"10"},
        )

        self.assertEqual(len(line_values), 2)
        self.assertEqual(
            line_items,
            [
                {"carton_id": 10},
                {"product": product, "quantity": 3},
            ],
        )
        self.assertEqual(line_errors, {})
