from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from wms.models import Carton, Shipment


class PrintLabelsViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-labels-user",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.factory = RequestFactory()

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_shipment(self):
        return Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

    def test_scan_shipment_labels_public_delegates_by_reference(self):
        from wms.views_print_labels import scan_shipment_labels_public

        shipment = self._create_shipment()
        request = self.factory.get("/scan/public-labels/")
        request.user = self.user
        with mock.patch(
            "wms.views_print_labels.render_shipment_labels",
            return_value=HttpResponse("ok"),
        ) as render_mock:
            response = scan_shipment_labels_public(request, shipment.reference)
        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(request, shipment)

    def test_scan_shipment_labels_delegates_by_id(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_labels.render_shipment_labels",
            return_value=HttpResponse("ok"),
        ) as render_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(mock.ANY, shipment)

    def test_scan_shipment_label_returns_404_when_carton_missing(self):
        shipment = self._create_shipment()
        response = self.client.get(
            reverse(
                "scan:scan_shipment_label",
                kwargs={"shipment_id": shipment.id, "carton_id": 999999},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_label_uses_dynamic_layout_when_override_exists(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-001", shipment=shipment)
        label_context = {
            "label_city": "Paris",
            "label_iata": "CDG",
            "label_shipment_ref": shipment.reference,
            "label_position": "1",
            "label_total": "1",
            "label_qr_url": "https://example.org/qr",
        }
        with mock.patch("wms.views_print_labels.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_print_labels.build_label_context",
                return_value=label_context,
            ):
                with mock.patch(
                    "wms.views_print_labels.get_template_layout",
                    return_value={"blocks": [{"id": "city"}]},
                ):
                    with mock.patch(
                        "wms.views_print_labels.render_layout_from_layout",
                        return_value=[{"type": "city"}],
                    ):
                        with mock.patch(
                            "wms.views_print_labels.render",
                            side_effect=self._render_stub,
                        ) as render_mock:
                            response = self.client.get(
                                reverse(
                                    "scan:scan_shipment_label",
                                    kwargs={
                                        "shipment_id": shipment.id,
                                        "carton_id": carton.id,
                                    },
                                )
                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/dynamic_labels.html")
        self.assertEqual(
            render_mock.call_args.args[2],
            {"labels": [{"blocks": [{"type": "city"}]}]},
        )

    def test_scan_shipment_label_uses_default_template_without_override(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-002", shipment=shipment)
        label_context = {
            "label_city": "Lyon",
            "label_iata": "LYS",
            "label_shipment_ref": shipment.reference,
            "label_position": "1",
            "label_total": "1",
            "label_qr_url": "",
        }
        with mock.patch("wms.views_print_labels.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_print_labels.build_label_context",
                return_value=label_context,
            ):
                with mock.patch(
                    "wms.views_print_labels.get_template_layout",
                    return_value=None,
                ):
                    with mock.patch(
                        "wms.views_print_labels.render",
                        side_effect=self._render_stub,
                    ) as render_mock:
                        response = self.client.get(
                            reverse(
                                "scan:scan_shipment_label",
                                kwargs={
                                    "shipment_id": shipment.id,
                                    "carton_id": carton.id,
                                },
                            )
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/etiquette_expedition.html")
        labels = render_mock.call_args.args[2]["labels"]
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["city"], "Lyon")
        self.assertEqual(labels[0]["carton_id"], carton.id)
