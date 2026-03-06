from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from wms.models import Carton, Shipment
from wms.print_pack_engine import PrintPackEngineError
from wms.print_pack_graph import GraphPdfConversionError
from wms.views_print_labels import (
    _build_default_label_payload,
    _find_carton_position,
    _generate_pack_xlsx_response,
    _render_shipment_label,
)


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
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=mock.Mock(name="artifact"),
            ) as generate_mock,
            mock.patch(
                "wms.views_print_labels._artifact_pdf_response",
                return_value=HttpResponse("ok"),
            ) as response_mock,
        ):
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
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=mock.Mock(name="artifact"),
            ) as generate_mock,
            mock.patch(
                "wms.views_print_labels._artifact_pdf_response",
                return_value=HttpResponse("ok"),
            ) as response_mock,
        ):
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

    def test_scan_shipment_labels_falls_back_to_legacy_renderer_when_pack_is_missing(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=PrintPackEngineError("Unknown active pack: D"),
            ),
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("legacy-labels"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy-labels")
        legacy_mock.assert_called_once_with(mock.ANY, shipment)

    def test_scan_shipment_labels_falls_back_to_legacy_renderer_on_graph_failure(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("legacy-labels"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy-labels")
        legacy_mock.assert_called_once_with(mock.ANY, shipment)

    @override_settings(PRINT_PACK_XLSX_FALLBACK_ENABLED=True)
    def test_scan_shipment_labels_returns_xlsx_fallback_on_graph_failure_when_enabled(
        self,
    ):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_labels._generate_pack_xlsx_response",
                return_value=HttpResponse("xlsx-fallback"),
            ) as xlsx_mock,
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("legacy-labels"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_labels",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "xlsx-fallback")
        xlsx_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            carton=None,
            variant="all_labels",
        )
        legacy_mock.assert_not_called()

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
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                return_value=mock.Mock(name="artifact"),
            ) as generate_mock,
            mock.patch(
                "wms.views_print_labels._artifact_pdf_response",
                return_value=HttpResponse("ok"),
            ) as response_mock,
        ):
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

    @override_settings(PRINT_PACK_XLSX_FALLBACK_ENABLED=True)
    def test_scan_shipment_label_returns_xlsx_fallback_on_graph_failure_when_enabled(
        self,
    ):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-001", shipment=shipment)
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_labels._generate_pack_xlsx_response",
                return_value=HttpResponse("xlsx-fallback"),
            ) as xlsx_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_label",
                    kwargs={"shipment_id": shipment.id, "carton_id": carton.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "xlsx-fallback")
        xlsx_mock.assert_called_once_with(
            pack_code="D",
            shipment=shipment,
            carton=carton,
            variant="single_label",
        )

    def test_find_carton_position_returns_none_when_missing(self):
        cartons = [mock.Mock(id=1), mock.Mock(id=2)]
        self.assertIsNone(_find_carton_position(cartons, carton_id=999))

    def test_render_shipment_label_uses_dynamic_layout_when_override_exists(self):
        request = self.factory.get("/scan/label/")
        label_context = {
            "label_city": "Paris",
            "label_iata": "CDG",
            "label_shipment_ref": "S-01",
            "label_position": 1,
            "label_total": 2,
            "label_qr_url": "",
            "carton_id": 1,
        }
        with (
            mock.patch(
                "wms.views_print_labels.get_template_layout",
                return_value={"blocks": ["x"]},
            ),
            mock.patch(
                "wms.views_print_labels.render_layout_from_layout",
                return_value=[{"type": "text", "value": "ok"}],
            ) as render_layout_mock,
            mock.patch(
                "wms.views_print_labels.render",
                return_value=HttpResponse("dynamic-label"),
            ) as render_mock,
        ):
            response = _render_shipment_label(request, label_context=label_context)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "dynamic-label")
        render_layout_mock.assert_called_once()
        render_mock.assert_called_once()

    def test_generate_pack_xlsx_response_builds_fallback_from_documents(self):
        with (
            mock.patch(
                "wms.views_print_labels.render_pack_xlsx_documents",
                return_value=[{"filename": "labels.xlsx", "content": b"x"}],
            ) as docs_mock,
            mock.patch(
                "wms.views_print_labels.build_xlsx_fallback_response",
                return_value=HttpResponse("xlsx"),
            ) as fallback_mock,
        ):
            response = _generate_pack_xlsx_response(
                pack_code="D",
                shipment=mock.Mock(),
                carton=mock.Mock(),
                variant="single_label",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "xlsx")
        docs_mock.assert_called_once()
        fallback_mock.assert_called_once()

    def test_build_default_label_payload_includes_carton_id(self):
        payload = _build_default_label_payload(
            {
                "label_city": "Paris",
                "label_iata": "CDG",
                "label_shipment_ref": "S-100",
                "label_position": 1,
                "label_total": 4,
                "label_qr_url": "",
            },
            carton_id=77,
        )
        self.assertEqual(payload[0]["carton_id"], 77)

    def test_scan_shipment_labels_public_falls_back_to_legacy_renderer_on_graph_failure(self):
        from wms.views_print_labels import scan_shipment_labels_public

        shipment = self._create_shipment()
        request = self.factory.get("/scan/public-labels/")
        request.user = self.user
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("legacy-public"),
            ) as legacy_mock,
        ):
            response = scan_shipment_labels_public(request, shipment.reference)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy-public")
        legacy_mock.assert_called_once_with(request, shipment)

    def test_scan_shipment_labels_public_falls_back_to_legacy_renderer_on_pack_error(self):
        from wms.views_print_labels import scan_shipment_labels_public

        shipment = self._create_shipment()
        request = self.factory.get("/scan/public-labels/")
        request.user = self.user
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=PrintPackEngineError("pack missing"),
            ),
            mock.patch(
                "wms.views_print_labels.render_shipment_labels",
                return_value=HttpResponse("legacy-public"),
            ) as legacy_mock,
        ):
            response = scan_shipment_labels_public(request, shipment.reference)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy-public")
        legacy_mock.assert_called_once_with(request, shipment)

    def test_scan_shipment_label_graph_fallback_raises_404_when_carton_not_in_ordered_set(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-404", shipment=shipment)
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_labels._find_carton_position",
                return_value=None,
            ),
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_label",
                    kwargs={"shipment_id": shipment.id, "carton_id": carton.id},
                )
            )

        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_label_falls_back_to_legacy_renderer_on_pack_error(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-LABEL-LEGACY", shipment=shipment)
        with (
            mock.patch(
                "wms.views_print_labels.generate_pack",
                side_effect=PrintPackEngineError("pack missing"),
            ),
            mock.patch(
                "wms.views_print_labels.build_label_context",
                return_value={
                    "label_city": "Paris",
                    "label_iata": "CDG",
                    "label_shipment_ref": "S-100",
                    "label_position": 1,
                    "label_total": 1,
                    "label_qr_url": "",
                },
            ),
            mock.patch(
                "wms.views_print_labels._render_shipment_label",
                return_value=HttpResponse("legacy-single"),
            ) as render_label_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_label",
                    kwargs={"shipment_id": shipment.id, "carton_id": carton.id},
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy-single")
        render_label_mock.assert_called_once()
