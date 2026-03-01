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
            "wms.views_print_labels.generate_pack",
            return_value=mock.Mock(name="artifact"),
        ) as generate_mock, mock.patch(
            "wms.views_print_labels._artifact_pdf_response",
            return_value=HttpResponse("ok"),
        ) as response_mock:
            response = scan_shipment_labels_public(request, shipment.reference)
        self.assertEqual(response.status_code, 200)
        generate_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            user=self.user,
            variant="all_labels",
        )
        response_mock.assert_called_once()

    def test_scan_shipment_labels_delegates_by_id(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_labels.generate_pack",
            return_value=mock.Mock(name="artifact"),
        ) as generate_mock, mock.patch(
            "wms.views_print_labels._artifact_pdf_response",
            return_value=HttpResponse("ok"),
        ) as response_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        generate_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            user=self.user,
            variant="all_labels",
        )
        response_mock.assert_called_once()

    def test_scan_shipment_label_returns_404_when_carton_missing(self):
        shipment = self._create_shipment()
        response = self.client.get(
            reverse(
                "scan:scan_shipment_label",
                kwargs={"shipment_id": shipment.id, "carton_id": 999999},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_label_routes_to_single_label_pack(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-001", shipment=shipment)
        with mock.patch(
            "wms.views_print_labels.generate_pack",
            return_value=mock.Mock(name="artifact"),
        ) as generate_mock, mock.patch(
            "wms.views_print_labels._artifact_pdf_response",
            return_value=HttpResponse("ok"),
        ) as response_mock:
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
        generate_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            carton=carton,
            user=self.user,
            variant="single_label",
        )
        response_mock.assert_called_once()
