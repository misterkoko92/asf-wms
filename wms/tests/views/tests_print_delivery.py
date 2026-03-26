from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from wms.models import Shipment
from wms.print_delivery import delivery_mode, wants_browser_print, wants_external_pdf


class PrintDeliveryModeTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_delivery_mode_defaults_to_html(self):
        request = self.factory.get("/scan/")
        self.assertEqual(delivery_mode(request), "html")
        self.assertFalse(wants_external_pdf(request))

    def test_delivery_mode_recognizes_pdf_query(self):
        request = self.factory.get("/scan/", {"delivery": "pdf"})
        self.assertEqual(delivery_mode(request), "pdf")
        self.assertTrue(wants_external_pdf(request))

    def test_wants_browser_print_honors_opt_in_html(self):
        request = self.factory.get("/scan/", {"delivery": "html"})
        self.assertEqual(delivery_mode(request), "html")
        self.assertTrue(wants_browser_print(request, default=False))


class PrintDeliveryRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-delivery-user",
            is_staff=True,
        )
        self.user.set_password("test-user-password")
        self.user.save(update_fields=["password"])
        self.client.force_login(self.user)

    def _create_shipment(self):
        return Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_scan_shipment_document_defaults_to_pdf_delivery_for_legacy_route(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("html-document"),
            ) as render_mock,
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                return_value=HttpResponse("pdf-document"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pdf-document")
        pdf_mock.assert_called_once_with(
            mock.ANY,
            pack_code="C",
            shipment=shipment,
            carton=None,
            variant="shipment",
        )
        render_mock.assert_not_called()

    def test_scan_shipment_document_honors_explicit_html_delivery(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("html-document"),
            ) as render_mock,
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                return_value=HttpResponse("pdf-document"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                ),
                {"delivery": "html"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "html-document")
        render_mock.assert_called_once_with(mock.ANY, shipment, "shipment_note")
        pdf_mock.assert_not_called()

    def test_scan_shipment_labels_defaults_to_pdf_delivery_for_legacy_route(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("html-labels"),
            ) as render_mock,
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=mock.Mock(name="artifact"),
            ) as generate_mock,
            mock.patch(
                "wms.views_print_labels._artifact_pdf_response",
                return_value=HttpResponse("pdf-labels"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pdf-labels")
        generate_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            user=self.user,
            variant="all_labels",
        )
        pdf_mock.assert_called_once()
        render_mock.assert_not_called()

    def test_scan_shipment_labels_honors_explicit_html_delivery(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("html-labels"),
            ) as render_mock,
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=mock.Mock(name="artifact"),
            ) as generate_mock,
            mock.patch(
                "wms.views_print_labels._artifact_pdf_response",
                return_value=HttpResponse("pdf-labels"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                ),
                {"delivery": "html"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "html-labels")
        render_mock.assert_called_once_with(mock.ANY, shipment)
        generate_mock.assert_not_called()
        pdf_mock.assert_not_called()
