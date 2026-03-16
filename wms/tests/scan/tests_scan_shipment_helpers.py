from django.test import TestCase
from django.utils import timezone

from wms.models import Shipment
from wms.scan_shipment_helpers import build_shipment_line_values, resolve_shipment


class ScanShipmentHelpersTests(TestCase):
    def test_build_shipment_line_values_populates_defaults(self):
        lines = build_shipment_line_values(2)
        self.assertEqual(
            lines,
            [
                {"carton_id": "", "product_code": "", "quantity": "", "expires_on": ""},
                {"carton_id": "", "product_code": "", "quantity": "", "expires_on": ""},
            ],
        )

    def test_build_shipment_line_values_reads_payload(self):
        data = {
            "line_1_carton_id": "12",
            "line_1_product_code": "SKU-1",
            "line_1_quantity": "3",
            "line_1_expires_on": "2026-02-01",
        }
        lines = build_shipment_line_values(1, data)
        self.assertEqual(lines[0]["carton_id"], "12")
        self.assertEqual(lines[0]["product_code"], "SKU-1")
        self.assertEqual(lines[0]["quantity"], "3")
        self.assertEqual(lines[0]["expires_on"], "2026-02-01")

    def test_resolve_shipment_matches_reference_case_insensitive(self):
        shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="10 Rue Test",
            destination_country="France",
        )
        self.assertEqual(resolve_shipment(shipment.reference.lower()).id, shipment.id)

    def test_resolve_shipment_ignorés_blank(self):
        self.assertIsNone(resolve_shipment(""))

    def test_resolve_shipment_ignores_archived(self):
        shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="10 Rue Test",
            destination_country="France",
            archived_at=timezone.now(),
        )
        self.assertIsNone(resolve_shipment(shipment.reference))
