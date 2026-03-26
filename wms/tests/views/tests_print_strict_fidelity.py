from unittest import mock

from django.test import RequestFactory, TestCase

from wms.models import Carton, Shipment
from wms.shipment_view_helpers import render_shipment_document, render_shipment_labels


class PrintStrictFidelityTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/scan/")

    def _create_shipment(self):
        return Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def test_render_donation_certificate_preserves_required_wording(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "donation_certificate")

        content = response.content.decode()
        self.assertIn("ATTESTATION DE DONATION", content)
        self.assertIn("Valeur uniquement pour la douane : 1.00 euro", content)
        self.assertIn('id="donation-certificate-title"', content)
        self.assertIn('id="donation-certificate-body"', content)

    def test_render_shipment_label_preserves_stable_visual_slots(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-STRICT-001", shipment=shipment)

        with (
            mock.patch.object(shipment, "ensure_qr_code"),
            mock.patch(
                "wms.shipment_view_helpers.build_label_context",
                return_value={
                    "label_city": "Paris",
                    "label_iata": "CDG",
                    "label_shipment_ref": shipment.reference,
                    "label_position": 1,
                    "label_total": 1,
                    "label_qr_url": "",
                },
            ),
            mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value=None,
            ),
        ):
            response = render_shipment_labels(self.request, shipment)

        content = response.content.decode()
        self.assertIn(f'id="shipment-label-city-{carton.id}"', content)
        self.assertIn(f'id="shipment-label-iata-{carton.id}"', content)
        self.assertIn(f'id="shipment-label-footer-{carton.id}"', content)
