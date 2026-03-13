from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from wms.models import (
    Carton,
    CartonItem,
    Location,
    Product,
    ProductLot,
    Shipment,
    Warehouse,
)
from wms.print_pack_engine import PrintPackEngineError
from wms.print_pack_graph import GraphPdfConversionError


class PrintDocsViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-docs-user",
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

    def _create_standalone_carton_with_item(self):
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="SKU-PRINT-DOCS",
            name="Produit Print",
            default_location=location,
            weight_g=500,
            volume_cm3=250,
            qr_code_image="qr_codes/test.png",
        )
        lot = ProductLot.objects.create(
            product=product,
            lot_code="LOT-PRINT",
            quantity_on_hand=10,
            location=location,
        )
        carton = Carton.objects.create(code="C-PRINT-001")
        CartonItem.objects.create(carton=carton, product_lot=lot, quantity=2)
        return carton

    def test_scan_shipment_document_routes_packed_doc_to_pack_engine(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                )
            )
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            mock.ANY,
            pack_code="C",
            shipment=shipment,
            carton=None,
            variant="shipment",
        )

    def test_scan_shipment_document_returns_helper_job_payload_when_requested(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_pack_xlsx_documents",
            return_value=[SimpleNamespace(filename="shipment-note.xlsx", payload=b"xlsx-data")],
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                ),
                {"helper": "1"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["output_filename"], f"print-pack-C-{shipment.reference}.pdf")
        self.assertTrue(payload["merge"] is False)
        self.assertEqual(payload["documents"][0]["filename"], "shipment-note.xlsx")
        self.assertIn("helper_document=0", payload["documents"][0]["download_url"])

    def test_scan_shipment_document_returns_helper_document_when_requested(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_pack_xlsx_documents",
            return_value=[SimpleNamespace(filename="shipment-note.xlsx", payload=b"xlsx-data")],
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                ),
                {"helper_document": "0"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(response.content, b"xlsx-data")

    def test_scan_shipment_document_public_routes_packed_doc_to_pack_engine(self):
        from wms.views_print_docs import scan_shipment_document_public

        shipment = self._create_shipment()
        request = self.factory.get("/scan/public/")
        request.user = self.user
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = scan_shipment_document_public(request, shipment.reference, "shipment_note")
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            request,
            pack_code="C",
            shipment=shipment,
            carton=None,
            variant="shipment",
        )

    def test_scan_shipment_document_falls_back_to_legacy_renderer_when_pack_is_missing(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                side_effect=PrintPackEngineError("Unknown active pack: C"),
            ),
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("legacy"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy")
        legacy_mock.assert_called_once_with(mock.ANY, shipment, "shipment_note")

    def test_scan_shipment_document_falls_back_to_legacy_renderer_on_graph_failure(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("legacy"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "legacy")
        legacy_mock.assert_called_once_with(mock.ANY, shipment, "shipment_note")

    @override_settings(PRINT_PACK_XLSX_FALLBACK_ENABLED=True)
    def test_scan_shipment_document_returns_xlsx_fallback_on_graph_failure_when_enabled(
        self,
    ):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                side_effect=GraphPdfConversionError("Graph is unavailable"),
            ),
            mock.patch(
                "wms.views_print_docs._generate_pack_xlsx_response",
                return_value=HttpResponse("xlsx-fallback"),
            ) as xlsx_mock,
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("legacy"),
            ) as legacy_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_document",
                    kwargs={"shipment_id": shipment.id, "doc_type": "shipment_note"},
                )
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "xlsx-fallback")
        xlsx_mock.assert_called_once_with(
            pack_code="C",
            shipment=shipment,
            carton=None,
            variant="shipment",
        )
        legacy_mock.assert_not_called()

    def test_scan_shipment_carton_document_404_when_carton_not_linked(self):
        shipment = self._create_shipment()
        response = self.client.get(
            reverse(
                "scan:scan_shipment_carton_document",
                kwargs={"shipment_id": shipment.id, "carton_id": 999999},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_carton_document_routes_to_pack_engine(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-SHIP-LOCAL", shipment=shipment)
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_carton_document",
                    kwargs={"shipment_id": shipment.id, "carton_id": carton.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            mock.ANY,
            pack_code="B",
            shipment=shipment,
            carton=carton,
            variant="per_carton_single",
        )

    def test_scan_shipment_carton_document_public_routes_to_pack_engine(self):
        from wms.views_print_docs import scan_shipment_carton_document_public

        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-SHIP-001", shipment=shipment)
        request = self.factory.get("/scan/public/")
        request.user = self.user
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = scan_shipment_carton_document_public(request, shipment.reference, carton.id)
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            request,
            pack_code="B",
            shipment=shipment,
            carton=carton,
            variant="per_carton_single",
        )

    def test_scan_shipment_carton_document_public_raises_404_when_missing(self):
        from wms.views_print_docs import scan_shipment_carton_document_public

        shipment = self._create_shipment()
        request = self.factory.get("/scan/public/")
        request.user = self.user
        with self.assertRaises(Http404):
            scan_shipment_carton_document_public(request, shipment.reference, 999999)

    def test_scan_carton_document_routes_to_pack_engine_when_carton_has_shipment(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-SHIP-DYN", shipment=shipment)
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_carton_document",
                    kwargs={"carton_id": carton.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            mock.ANY,
            pack_code="B",
            shipment=shipment,
            carton=carton,
            variant="per_carton_single",
        )

    def test_scan_carton_document_routes_to_pack_engine_without_shipment(self):
        carton = self._create_standalone_carton_with_item()
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = self.client.get(
                reverse("scan:scan_carton_document", kwargs={"carton_id": carton.id})
            )
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            mock.ANY,
            pack_code="B",
            shipment=None,
            carton=carton,
            variant="per_carton_single",
        )

    def test_scan_carton_document_builds_fallback_context_without_shipment_when_pack_fails(
        self,
    ):
        carton = self._create_standalone_carton_with_item()
        with (
            mock.patch(
                "wms.views_print_docs._generate_pack_pdf_response",
                side_effect=PrintPackEngineError("missing pack"),
            ),
            mock.patch(
                "wms.views_print_docs.get_template_layout",
                return_value=None,
            ),
            mock.patch(
                "wms.views_print_docs.render",
                side_effect=self._render_stub,
            ) as render_mock,
        ):
            response = self.client.get(
                reverse("scan:scan_carton_document", kwargs={"carton_id": carton.id})
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "print/liste_colisage_carton.html")
        context = render_mock.call_args.args[2]
        self.assertEqual(context["shipment_ref"], "-")
        self.assertEqual(context["carton_code"], carton.code)
        self.assertEqual(len(context["item_rows"]), 1)
        self.assertEqual(context["item_rows"][0]["quantity"], 2)
        self.assertEqual(context["item_rows"][0]["lot"], "LOT-PRINT")
        self.assertEqual(context["carton_weight_kg"], 1.0)
        self.assertTrue(context["hide_footer"])

    def test_scan_carton_picking_routes_to_pack_engine(self):
        carton = self._create_standalone_carton_with_item()
        with mock.patch(
            "wms.views_print_docs._generate_pack_pdf_response",
            return_value=HttpResponse("ok"),
        ) as pack_mock:
            response = self.client.get(
                reverse("scan:scan_carton_picking", kwargs={"carton_id": carton.id})
            )
        self.assertEqual(response.status_code, 200)
        pack_mock.assert_called_once_with(
            mock.ANY,
            pack_code="A",
            shipment=None,
            carton=carton,
            variant="single_carton",
        )

    def test_scan_shipment_document_upload_delegates_to_handler(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.handle_shipment_document_upload",
            return_value=HttpResponse("uploaded"),
        ) as upload_mock:
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_document_upload",
                    kwargs={"shipment_id": shipment.id},
                )
            )
        self.assertEqual(response.status_code, 200)
        upload_mock.assert_called_once_with(mock.ANY, shipment_id=shipment.id)

    def test_scan_shipment_document_delete_delegates_to_handler(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.handle_shipment_document_delete",
            return_value=HttpResponse("deleted"),
        ) as delete_mock:
            response = self.client.post(
                reverse(
                    "scan:scan_shipment_document_delete",
                    kwargs={"shipment_id": shipment.id, "document_id": 42},
                )
            )
        self.assertEqual(response.status_code, 200)
        delete_mock.assert_called_once_with(mock.ANY, shipment_id=shipment.id, document_id=42)

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_carton_packing_list_template_uses_native_english(self):
        context = {
            "carton_code": "C-PRINT-EN",
            "carton_weight_kg": 1.25,
            "item_rows": [
                {
                    "product": "Printed product",
                    "quantity": 2,
                    "expires_on": None,
                }
            ],
        }

        with translation.override("en"):
            body = render_to_string("print/liste_colisage_carton.html", context)

        self.assertIn("Packing list - carton", body)
        self.assertIn("Head office", body)
        self.assertNotIn("Liste de colisage - carton", body)
        self.assertNotIn("Siege :", body)

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_print_templates_keep_french_source_strings_and_translate_to_english(self):
        attestation_context = {
            "document_ref": "DOC-001",
            "document_date": None,
            "org_name": "ASF",
            "org_address": "1 Rue Test",
            "org_contact": "Contact",
            "shipper_name": "Shipper",
            "recipient_name": "Recipient",
            "destination_address": "Paris",
            "humanitarian_purpose": "Aide",
            "donor_name": "Donor",
            "donation_description": "Donation",
            "shipment_description": "Shipment",
            "org_signatory": "Signer",
        }
        carton_context = {
            "carton_code": "C-PRINT-FR",
            "carton_weight_kg": 1.25,
            "item_rows": [
                {
                    "product": "Produit imprime",
                    "quantity": 2,
                    "expires_on": None,
                }
            ],
        }
        picking_context = {
            "carton_code": "C-PICK-FR",
            "item_rows": [{"label": "Produit", "quantity": 2, "location": "A-01-001"}],
        }

        with translation.override("fr"):
            attestation = render_to_string(
                "print/attestation_aide_humanitaire.html",
                attestation_context,
            )
            donation = render_to_string(
                "print/attestation_donation.html",
                attestation_context,
            )
            customs = render_to_string(
                "print/attestation_douane.html",
                attestation_context,
            )
            carton = render_to_string("print/liste_colisage_carton.html", carton_context)
            picking = render_to_string("print/picking_list_carton.html", picking_context)
        with translation.override("en"):
            attestation_en = render_to_string(
                "print/attestation_aide_humanitaire.html",
                attestation_context,
            )
            carton_en = render_to_string("print/liste_colisage_carton.html", carton_context)
            picking_en = render_to_string("print/picking_list_carton.html", picking_context)

        self.assertIn("Réf document", attestation)
        self.assertNotIn("Document ref", attestation)
        self.assertIn("Réf document", donation)
        self.assertNotIn("Document ref", donation)
        self.assertIn("Réf document", customs)
        self.assertNotIn("Document ref", customs)
        self.assertIn("Code carton", carton)
        self.assertNotIn("Carton code", carton)
        self.assertIn("Code carton", picking)
        self.assertNotIn("Carton code", picking)
        self.assertIn("Document ref", attestation_en)
        self.assertNotIn("Réf document", attestation_en)
        self.assertIn("Carton code", carton_en)
        self.assertNotIn("Code carton", carton_en)
        self.assertIn("Carton code", picking_en)
        self.assertNotIn("Code carton", picking_en)
