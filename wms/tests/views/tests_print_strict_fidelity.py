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
        self.assertIn("@page { size: A5 landscape; margin: 8mm; }", content)
        self.assertIn('id="donation-certificate-header"', content)
        self.assertIn('class="certificate-city certificate-accent"', content)
        self.assertIn("1 Rue Test - France", content)
        self.assertNotIn("1 Rue Test<br>France", content)
        self.assertIn('id="donation-certificate-notes"', content)
        self.assertIn('id="donation-certificate-customs-value"', content)
        self.assertIn('id="donation-certificate-signoff"', content)
        self.assertIn('id="donation-certificate-signoff-lines"', content)
        self.assertIn("certificate-emphasis", content)
        self.assertNotIn("Code Postal :", content)
        self.assertNotIn("Ville :", content)
        self.assertNotIn("Pays :", content)
        self.assertNotIn('class="print-footer"', content)

    def test_render_shipment_note_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "shipment_note")

        content = response.content.decode()
        self.assertIn('id="shipment-note-sheet"', content)
        self.assertIn('id="shipment-note-header"', content)
        self.assertIn('id="shipment-note-routing-primary"', content)
        self.assertIn('id="shipment-note-routing-secondary"', content)
        self.assertIn('id="shipment-note-parties"', content)
        self.assertIn("sheet-party-grid", content)
        self.assertIn("sheet-routing-table", content)
        self.assertIn("sheet-party-table", content)
        self.assertIn("sheet-emphasis-row", content)
        self.assertIn("NUMERO D'EXPEDITION /", content)
        self.assertIn("Expedition number", content)
        self.assertIn("EXPEDITEUR /", content)
        self.assertIn("Shipper", content)
        self.assertIn("CORRESPONDANT /", content)
        self.assertIn("Local Agent", content)
        self.assertIn("RESPONSABLE VOL ASF /", content)
        self.assertIn("ASF Flight Manager", content)
        self.assertIn("@page { size: A4 landscape; margin: 8mm; }", content)
        self.assertIn("sheet-en", content)
        self.assertIn("sheet-highlight", content)
        self.assertNotIn('class="print-footer"', content)

    def test_render_customs_note_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "customs")

        content = response.content.decode()
        self.assertIn('id="customs-note-sheet"', content)
        self.assertIn('id="customs-note-header"', content)
        self.assertIn('id="customs-note-routing-primary"', content)
        self.assertIn('id="customs-note-routing-secondary"', content)
        self.assertIn('id="customs-note-parties"', content)
        self.assertIn("sheet-party-grid", content)
        self.assertIn("sheet-routing-table", content)
        self.assertIn("sheet-party-table", content)
        self.assertIn("sheet-emphasis-row", content)
        self.assertIn("VISA DOUANE /", content)
        self.assertIn("Customs date", content)
        self.assertIn("RESP. DOUANE ASF /", content)
        self.assertIn("ASF Customs agent", content)
        self.assertIn("These parcels have all been verified by X-ray", content)
        self.assertIn("@page { size: A4 landscape; margin: 8mm; }", content)
        self.assertIn("sheet-en", content)
        self.assertIn("sheet-highlight", content)
        self.assertNotIn('class="print-footer"', content)

    def test_render_shipment_packing_list_preserves_legacy_sheet_sections(self):
        shipment = self._create_shipment()

        response = render_shipment_document(self.request, shipment, "packing_list_shipment")

        content = response.content.decode()
        self.assertIn('id="packing-list-shipment-sheet"', content)
        self.assertIn("@page { size: A5 landscape; margin: 8mm; }", content)
        self.assertIn('id="packing-list-shipment-header"', content)
        self.assertIn("packing-sheet-logo", content)
        self.assertIn("packing-list-shipment-table", content)
        self.assertIn("packing-col-product", content)
        self.assertIn("packing-col-carton", content)
        self.assertIn("packing-col-quantity", content)
        self.assertIn("packing-col-expiry", content)
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
        self.assertIn("@page { size: landscape; margin: 8mm; }", content)
        self.assertIn('id="packing-list-carton-header"', content)
        self.assertIn("packing-list-carton-table", content)
        self.assertIn("packing-col-product", content)
        self.assertIn("packing-col-quantity", content)
        self.assertIn("packing-col-expiry", content)
        self.assertIn("packing-sheet-logo", content)
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
        self.assertIn("EXP N°", content)
        self.assertIn("Colis /", content)
        self.assertIn("Parcel", content)
        self.assertIn("label-iata-wrap", content)
        self.assertIn("label-qr-wrap", content)
