from unittest import mock

from django.test import RequestFactory, TestCase

from wms.models import Carton, Shipment
from wms.shipment_view_helpers import (
    render_carton_document,
    render_shipment_document,
    render_shipment_labels,
)


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
        self.assertIn("Je soussigné :", content)
        self.assertIn("De l'Association :", content)
        self.assertIn("Valeur uniquement pour la douane : 1.00 euro", content)
        self.assertIn('id="donation-certificate-title"', content)
        self.assertIn('id="donation-certificate-body"', content)

    def test_render_shipment_note_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "shipment_note")

        content = response.content.decode()
        self.assertIn('id="shipment-note-sheet"', content)
        self.assertIn("NUMERO D'EXPEDITION / Expedition number", content)
        self.assertIn("EXPEDITEUR / Shipper", content)
        self.assertIn("CORRESPONDANT / Local Agent", content)
        self.assertIn("RESPONSABLE VOL ASF / ASF Flight Manager", content)

    def test_render_customs_note_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "customs")

        content = response.content.decode()
        self.assertIn('id="customs-note-sheet"', content)
        self.assertIn("VISA DOUANE / Customs date", content)
        self.assertIn("RESP. DOUANE ASF / ASF Customs agent", content)
        self.assertIn("These parcels have all been verified by X-ray", content)

    def test_render_shipment_packing_list_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "packing_list_shipment")

        content = response.content.decode()
        self.assertIn('id="packing-list-shipment-sheet"', content)
        self.assertIn("LISTE DE COLISAGE", content)
        self.assertIn(
            "Dons humanitaires non destinés à être revendus - Produits non dangereux", content
        )
        self.assertIn("N° DE LOT", content)
        self.assertIn("COLIS N°", content)

    def test_render_carton_packing_list_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-PL-001", shipment=shipment)

        response = render_carton_document(self.request, shipment, carton)

        content = response.content.decode()
        self.assertIn('id="packing-list-carton-sheet"', content)
        self.assertIn("LISTE DE COLISAGE", content)
        self.assertIn("Référence du colis :", content)
        self.assertIn("DATE LIMITE", content)

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
