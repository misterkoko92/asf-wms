from unittest import mock

from django.test import RequestFactory, TestCase

from wms.models import Carton, Shipment
from wms.shipment_view_helpers import (
    render_carton_document,
    render_shipment_document,
    render_shipment_labels,
)


class PrintTemplatesRenderingTests(TestCase):
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

    def test_render_shipment_document_uses_document_print_surface(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.shipment_view_helpers.build_shipment_document_context",
                return_value={
                    "shipment_ref": shipment.reference,
                    "hide_footer": True,
                    "destination_address": shipment.destination_address,
                    "destination_city": "",
                    "destination_iata": "",
                    "carton_count": 0,
                    "weight_total_g": 0,
                    "weight_total_kg": 0,
                    "type_labels": "",
                    "shipper_info": {},
                    "recipient_info": {},
                    "correspondent_info": {},
                    "document_date": None,
                },
            ),
            mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value=None,
            ),
        ):
            response = render_shipment_document(self.request, shipment, "shipment_note")

        content = response.content.decode()
        self.assertIn('data-print-surface="document"', content)

    def test_render_carton_document_uses_document_print_surface(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-200", shipment=shipment)

        with (
            mock.patch(
                "wms.shipment_view_helpers.build_carton_document_context",
                return_value={"carton_code": carton.code, "hide_footer": True, "item_rows": []},
            ),
            mock.patch(
                "wms.shipment_view_helpers.get_template_layout",
                return_value=None,
            ),
        ):
            response = render_carton_document(self.request, shipment, carton)

        content = response.content.decode()
        self.assertIn('data-print-surface="document"', content)

    def test_render_shipment_labels_uses_label_print_surface(self):
        shipment = self._create_shipment()
        Carton.objects.create(code="A-CARTON", shipment=shipment)

        with (
            mock.patch.object(shipment, "ensure_qr_code"),
            mock.patch(
                "wms.shipment_view_helpers.build_label_context",
                return_value={
                    "label_city": "Paris",
                    "label_iata": "CDG",
                    "label_shipment_ref": shipment.reference,
                    "label_position": "1",
                    "label_total": "1",
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
        self.assertIn('data-print-surface="label"', content)
