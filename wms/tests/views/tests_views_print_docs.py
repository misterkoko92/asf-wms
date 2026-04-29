from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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

    def _create_shipment_with_cartons(self, *codes):
        shipment = self._create_shipment()
        cartons = []
        for code in codes:
            cartons.append(Carton.objects.create(code=code, shipment=shipment))
        return shipment, cartons

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
                ),
                {"delivery": "pdf"},
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
        self.assertEqual(
            payload["required_capabilities"],
            ["pdf_render", "excel_render"],
        )

    def test_scan_shipment_document_requires_pdf_merge_for_multi_document_helper_job(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_pack_xlsx_documents",
            return_value=[
                SimpleNamespace(filename="shipment-note-1.xlsx", payload=b"xlsx-data-1"),
                SimpleNamespace(filename="shipment-note-2.xlsx", payload=b"xlsx-data-2"),
            ],
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
        self.assertTrue(payload["merge"])
        self.assertEqual(
            payload["required_capabilities"],
            ["pdf_render", "excel_render", "pdf_merge"],
        )

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
                ),
                {"delivery": "pdf"},
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
                ),
                {"delivery": "pdf"},
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
                ),
                {"delivery": "pdf"},
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

    def test_scan_shipment_view_document_routes_shipment_note_to_html_template(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_shipment_document",
            return_value=HttpResponse("shipment-note-html"),
        ) as render_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "shipment_note"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            mock.ANY,
            shipment,
            "shipment_note",
        )
        self.assertEqual(response.content.decode(), "shipment-note-html")

    def test_scan_shipment_view_document_routes_customs_to_html_template(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_shipment_document",
            return_value=HttpResponse("customs-html"),
        ) as render_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "customs"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            mock.ANY,
            shipment,
            "customs",
        )
        self.assertEqual(response.content.decode(), "customs-html")

    def test_scan_shipment_view_document_routes_packing_list_to_html_template(self):
        shipment = self._create_shipment()
        with mock.patch(
            "wms.views_print_docs.render_shipment_document",
            return_value=HttpResponse("packing-list-html"),
        ) as render_mock:
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "packing_list"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            mock.ANY,
            shipment,
            "packing_list_shipment",
        )
        self.assertEqual(response.content.decode(), "packing-list-html")

    def test_scan_shipment_view_document_routes_donation_per_carton_in_code_order(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")
        with (
            mock.patch(
                "wms.views_print_docs.render_pack_document_xlsx_documents",
                return_value=[SimpleNamespace(filename="donation-1.xlsx", payload=b"xlsx-1")],
            ) as render_mock,
            mock.patch(
                "wms.views_print_docs._build_pdf_response_from_xlsx_documents",
                return_value=HttpResponse("pdf"),
            ),
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "donation"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            pack_code="B",
            doc_type="donation_certificate",
            variant="shipment",
            shipment=shipment,
            cartons=[cartons[1], cartons[0]],
        )

    def test_scan_shipment_view_document_routes_contact_to_html_template(self):
        shipment = self._create_shipment()
        with (
            mock.patch(
                "wms.views_print_docs.render_shipment_document",
                return_value=HttpResponse("contact-html"),
            ) as render_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "contact"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            mock.ANY,
            shipment,
            "contact_label",
        )
        self.assertEqual(response.content.decode(), "contact-html")

    def test_scan_shipment_view_bundle_routes_paper_to_direct_printable_html(self):
        shipment = self._create_shipment()

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "paper"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-paper-print-document"')
        self.assertNotContains(response, 'id="shipment-paper-bundle"')
        self.assertNotContains(response, 'class="scan-scan-btn btn btn-tertiary"')
        content = response.content.decode()
        self.assertLess(
            content.index('id="shipment-paper-section-shipment_note"'),
            content.index('id="shipment-paper-section-customs"'),
        )
        self.assertLess(
            content.index('id="shipment-paper-section-customs"'),
            content.index('id="shipment-paper-section-packing_list_copy_1"'),
        )
        self.assertLess(
            content.index('id="shipment-paper-section-packing_list_copy_1"'),
            content.index('id="shipment-paper-section-packing_list_copy_2"'),
        )
        self.assertContains(response, 'id="shipment-note-sheet"')
        self.assertContains(response, 'id="customs-note-sheet"')
        self.assertContains(response, 'id="packing-list-shipment-sheet-copy-1"')
        self.assertContains(response, 'id="packing-list-shipment-sheet-copy-2"')
        self.assertContains(response, 'class="paper-bundle-section"', count=4)
        self.assertIn("grid-template-columns: 32mm 1fr;", content)
        self.assertIn("width: 32mm;", content)
        self.assertIn("grid-template-columns: 28mm 1fr 28mm;", content)
        self.assertIn("width: 28mm;", content)
        self.assertIn('class="packing-shipment-ref-value"', content)
        self.assertIn(".customs-note {", content)
        self.assertIn("font-size: 11pt;", content)
        self.assertIn("font-weight: 800;", content)

    def test_scan_shipment_view_bundle_routes_carton_lists_to_html_bundle_page(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "carton_lists"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-carton-lists-bundle"')
        self.assertContains(response, "Lot rouleau continu")
        self.assertContains(response, cartons[0].code)
        self.assertContains(response, cartons[1].code)
        self.assertContains(response, "Liste colisage")
        self.assertContains(
            response,
            f'{reverse("scan:scan_shipment_carton_document", args=[shipment.id, cartons[0].id])}?delivery=html',
        )
        self.assertContains(
            response,
            f'{reverse("scan:scan_shipment_carton_document", args=[shipment.id, cartons[1].id])}?delivery=html',
        )

    def test_scan_shipment_view_bundle_routes_carton_lists_a4_to_direct_printable_html(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "carton_lists_a4"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-carton-lists-a4-print-document"')
        self.assertContains(response, "Lot listes colisage A4")
        self.assertContains(response, 'class="packing-four-up-pages"')
        self.assertContains(response, 'class="packing-four-up-page"', count=1)
        self.assertContains(response, cartons[0].code)
        self.assertContains(response, cartons[1].code)
        self.assertNotContains(response, 'id="shipment-carton-lists-a4-bundle"')

    def test_scan_shipment_view_bundle_routes_standard_labels_to_direct_printable_html(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "standard_labels"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-carton-documents-print-document"')
        self.assertNotContains(response, 'id="shipment-carton-documents-bundle"')
        self.assertNotContains(response, 'class="scan-scan-btn btn btn-tertiary"')
        content = response.content.decode()
        self.assertContains(response, 'class="carton-documents-page"', count=2)
        self.assertContains(response, 'data-print-doc-type="donation_certificate"', count=2)
        self.assertContains(response, 'data-print-doc-type="shipment_label"', count=2)
        self.assertContains(response, 'data-print-doc-type="contact_label"', count=2)
        self.assertContains(response, 'data-print-doc-type="packing_list_carton"', count=2)
        self.assertLess(
            content.index(f'id="shipment-carton-documents-page-{cartons[1].id}"'),
            content.index(f'id="shipment-carton-documents-page-{cartons[0].id}"'),
        )
        self.assertContains(response, 'id="contact-label"')
        self.assertContains(response, 'id="shipment-label-')
        self.assertContains(response, 'id="donation-certificate-sheet"')
        self.assertContains(response, 'id="packing-list-carton-table-')
        self.assertContains(response, "Téléphone")
        self.assertNotContains(response, "TELEPHONE")
        self.assertContains(response, "font-size: 23pt;")
        self.assertContains(response, "font-size: 34pt;")
        self.assertContains(response, "font-size: 20pt;")
        self.assertContains(response, "@page { size: A4 portrait; margin: 0; }")
        self.assertContains(response, "grid-template-columns: repeat(2, 105mm);")
        self.assertContains(response, "grid-template-rows: repeat(2, 148.5mm);")
        self.assertContains(response, "width: 105mm;")
        self.assertContains(response, "height: 148.5mm;")
        self.assertContains(response, "--label-iata-block-width: 52mm;")
        self.assertContains(response, "width: var(--label-iata-block-width);")
        self.assertContains(response, "height: var(--label-iata-block-width);")
        self.assertContains(response, "flex: 0 0 38%;")
        self.assertContains(response, "max-width: 38%;")
        self.assertNotContains(response, "flex: 0 0 25%;")
        self.assertNotContains(response, "flex: 0 0 33%;")
        self.assertNotContains(response, "max-width: 33%;")
        self.assertContains(response, "grid-template-columns: 1fr;")
        self.assertContains(response, "width: 22mm;")
        self.assertContains(response, "width: 33%;")
        self.assertContains(response, '<span class="label-box-text">N° 1 / 2</span>')
        self.assertContains(response, '<span class="label-box-text">N° 2 / 2</span>')
        self.assertNotContains(response, "Colis /")
        self.assertNotContains(response, "Parcel")

    def test_scan_shipment_view_bundle_routes_preparatory_labels(self):
        shipment = self._create_shipment()
        shipment.planned_carton_count = 3
        shipment.save(update_fields=["planned_carton_count"])

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "preparatory_labels"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-preparatory-labels-print-document"')
        self.assertContains(response, 'class="carton-documents-page"', count=3)
        self.assertContains(response, 'data-print-doc-type="donation_certificate"', count=3)
        self.assertContains(response, 'data-print-doc-type="shipment_label"', count=3)
        self.assertContains(response, 'data-print-doc-type="contact_label"', count=3)
        self.assertNotContains(response, 'data-print-doc-type="packing_list_carton"')
        self.assertContains(response, '<span class="label-box-text">N° 1 / 3</span>')
        self.assertContains(response, '<span class="label-box-text">N° 3 / 3</span>')

    def test_scan_shipment_batch_view_bundle_paper_renders_all_shipments(self):
        shipment_a = self._create_shipment()
        shipment_b = self._create_shipment()

        response = self.client.get(
            reverse("scan:scan_shipment_batch_view_bundle", kwargs={"bundle_key": "paper"}),
            {"shipment_ids": f"{shipment_a.id},{shipment_b.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-batch-paper-print-document"')
        self.assertContains(response, shipment_a.reference)
        self.assertContains(response, shipment_b.reference)

    def test_scan_shipment_batch_view_bundle_preparatory_labels_renders_all_shipments(self):
        shipment_a = self._create_shipment()
        shipment_a.planned_carton_count = 2
        shipment_a.save(update_fields=["planned_carton_count"])
        shipment_b = self._create_shipment()
        shipment_b.planned_carton_count = 1
        shipment_b.save(update_fields=["planned_carton_count"])

        response = self.client.get(
            reverse(
                "scan:scan_shipment_batch_view_bundle",
                kwargs={"bundle_key": "preparatory_labels"},
            ),
            {"shipment_ids": f"{shipment_a.id},{shipment_b.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-batch-preparatory-labels-print-document"')
        self.assertContains(response, shipment_a.reference)
        self.assertContains(response, shipment_b.reference)
        self.assertContains(response, 'data-print-doc-type="shipment_label"', count=3)
        self.assertNotContains(response, 'data-print-doc-type="packing_list_carton"')

    def test_scan_shipment_batch_view_bundle_404_without_shipment_ids(self):
        response = self.client.get(
            reverse("scan:scan_shipment_batch_view_bundle", kwargs={"bundle_key": "paper"})
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_batch_view_bundle_404_when_only_archived_shipments_match(self):
        shipment = self._create_shipment()
        shipment.archived_at = timezone.now()
        shipment.save(update_fields=["archived_at"])

        response = self.client.get(
            reverse("scan:scan_shipment_batch_view_bundle", kwargs={"bundle_key": "paper"}),
            {"shipment_ids": str(shipment.id)},
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_batch_view_bundle_404_for_unknown_bundle_key(self):
        shipment = self._create_shipment()

        response = self.client.get(
            reverse("scan:scan_shipment_batch_view_bundle", kwargs={"bundle_key": "unknown"}),
            {"shipment_ids": str(shipment.id)},
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_cartons_view_bundle_routes_packing_lists_to_html_bundle_page(self):
        carton_a = self._create_standalone_carton_with_item()
        carton_a.code = "C-BUNDLE-A"
        carton_a.save(update_fields=["code"])
        product_lot = carton_a.cartonitem_set.first().product_lot
        carton_b = Carton.objects.create(code="C-BUNDLE-B")
        CartonItem.objects.create(carton=carton_b, product_lot=product_lot, quantity=1)

        response = self.client.get(
            reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"}),
            {"carton_ids": f"{carton_a.id},{carton_b.id}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="carton-packing-lists-bundle"')
        self.assertContains(response, "Lot listes colisage")
        self.assertContains(response, "C-BUNDLE-A")
        self.assertContains(response, "C-BUNDLE-B")
        self.assertContains(response, "Liste colisage")
        self.assertContains(
            response,
            f'{reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"})}?carton_ids={carton_a.id},{carton_b.id}&amp;format=continuous',
        )
        self.assertContains(
            response,
            f'{reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"})}?carton_ids={carton_a.id},{carton_b.id}&amp;format=a4_4up',
        )
        self.assertContains(
            response,
            f'{reverse("scan:scan_carton_document", args=[carton_a.id])}?delivery=html',
        )
        self.assertContains(
            response,
            f'{reverse("scan:scan_carton_document", args=[carton_b.id])}?delivery=html',
        )

    def test_scan_cartons_view_bundle_routes_packing_lists_to_continuous_print_document(self):
        carton_a = self._create_standalone_carton_with_item()
        carton_a.code = "C-CONT-A"
        carton_a.save(update_fields=["code"])
        product_lot = carton_a.cartonitem_set.first().product_lot
        carton_b = Carton.objects.create(code="C-CONT-B")
        CartonItem.objects.create(carton=carton_b, product_lot=product_lot, quantity=1)

        response = self.client.get(
            reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"}),
            {"carton_ids": f"{carton_a.id},{carton_b.id}", "format": "continuous"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="carton-packing-lists-print-document"')
        self.assertContains(response, "C-CONT-A")
        self.assertContains(response, "C-CONT-B")
        self.assertEqual(response.content.decode().count('class="packing-sheet"'), 2)

    def test_scan_cartons_view_bundle_routes_packing_lists_to_a4_four_up_print_document(self):
        carton_a = self._create_standalone_carton_with_item()
        carton_a.code = "C-A4-A"
        carton_a.save(update_fields=["code"])
        product_lot = carton_a.cartonitem_set.first().product_lot
        carton_b = Carton.objects.create(code="C-A4-B")
        CartonItem.objects.create(carton=carton_b, product_lot=product_lot, quantity=1)

        response = self.client.get(
            reverse("scan:scan_cartons_view_bundle", kwargs={"bundle_key": "packing_lists"}),
            {"carton_ids": f"{carton_a.id},{carton_b.id}", "format": "a4_4up"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-carton-lists-a4-print-document"')
        self.assertContains(response, "C-A4-A")
        self.assertContains(response, "C-A4-B")
        self.assertEqual(response.content.decode().count('class="packing-four-up-item"'), 2)

    def test_scan_shipment_view_bundle_routes_all_to_orchestrator_page(self):
        shipment = self._create_shipment()

        response = self.client.get(
            reverse(
                "scan:scan_shipment_view_bundle",
                kwargs={"shipment_id": shipment.id, "bundle_key": "all"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shipment-print-bundle"')
        self.assertContains(response, "Lot papier A4")
        self.assertContains(response, "Lot rouleau continu")
        self.assertContains(response, "Lot A4 4 par page")
        self.assertContains(response, "Lot étiquettes cartons")

    def test_scan_shipment_donation_certificate_renders_locked_template(self):
        shipment = self._create_shipment()
        carton = Carton.objects.create(code="C-DON-001", shipment=shipment)

        response = self.client.get(
            reverse(
                "scan:scan_shipment_donation_certificate",
                kwargs={"shipment_id": shipment.id, "carton_id": carton.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="donation-certificate-title"')
        self.assertContains(response, "ATTESTATION DE DONATION")

    def test_scan_shipment_donation_certificate_returns_404_when_carton_missing(self):
        shipment = self._create_shipment()

        response = self.client.get(
            reverse(
                "scan:scan_shipment_donation_certificate",
                kwargs={"shipment_id": shipment.id, "carton_id": 999999},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_view_document_routes_single_labels_per_carton(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")
        with (
            mock.patch(
                "wms.views_print_docs.render_pack_document_xlsx_documents",
                return_value=[SimpleNamespace(filename="label-1.xlsx", payload=b"xlsx-1")],
            ) as render_mock,
            mock.patch(
                "wms.views_print_docs._build_pdf_response_from_xlsx_documents",
                return_value=HttpResponse("pdf"),
            ),
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "labels"},
                )
            )

        self.assertEqual(response.status_code, 200)
        render_mock.assert_called_once_with(
            pack_code="D",
            doc_type="destination_label",
            variant="single_label",
            shipment=shipment,
            cartons=[cartons[1], cartons[0]],
        )

    def test_scan_shipment_view_document_returns_helper_job_payload_for_multi_carton_donation(
        self,
    ):
        shipment, _cartons = self._create_shipment_with_cartons("C-001", "C-002")
        with mock.patch(
            "wms.views_print_docs.render_pack_document_xlsx_documents",
            return_value=[
                SimpleNamespace(filename="donation-1.xlsx", payload=b"xlsx-1"),
                SimpleNamespace(filename="donation-2.xlsx", payload=b"xlsx-2"),
            ],
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_document",
                    kwargs={"shipment_id": shipment.id, "document_key": "donation"},
                ),
                {"helper": "1"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["output_filename"], f"print-pack-B-{shipment.reference}.pdf")
        self.assertTrue(payload["merge"])
        self.assertEqual(len(payload["documents"]), 2)
        self.assertEqual(
            payload["required_capabilities"],
            ["pdf_render", "excel_render", "pdf_merge"],
        )

    def test_build_shipment_view_bundle_a5_xlsx_documents_orders_documents_by_bundle_rules(self):
        shipment, cartons = self._create_shipment_with_cartons("C-020", "C-010")

        def _render_side_effect(*, pack_code, doc_type, variant, shipment, cartons):  # noqa: ARG001
            suffix = "shipment" if cartons is None else "-".join(carton.code for carton in cartons)
            return [
                SimpleNamespace(filename=f"{pack_code}-{doc_type}-{suffix}.xlsx", payload=b"xlsx")
            ]

        with mock.patch(
            "wms.views_print_docs.render_pack_document_xlsx_documents",
            side_effect=_render_side_effect,
        ):
            from wms.views_print_docs import _build_shipment_view_bundle_a5_xlsx_documents

            documents = _build_shipment_view_bundle_a5_xlsx_documents(shipment)

        self.assertEqual(
            [entry.filename for entry in documents],
            [
                "B-packing_list_shipment-shipment.xlsx",
                "B-donation_certificate-C-010.xlsx",
                "D-destination_label-C-010.xlsx",
                "C-contact_label-C-010.xlsx",
                "B-donation_certificate-C-020.xlsx",
                "D-destination_label-C-020.xlsx",
                "C-contact_label-C-020.xlsx",
            ],
        )

    def test_build_shipment_view_bundle_a4_xlsx_documents_orders_documents_by_bundle_rules(self):
        shipment = self._create_shipment()

        def _render_side_effect(
            *,
            pack_code,
            doc_type,
            variant,
            shipment,
            cartons,
            render_doc_type=None,
        ):  # noqa: ARG001
            effective_doc_type = render_doc_type or doc_type
            suffix = "shipment" if cartons is None else "-".join(carton.code for carton in cartons)
            return [
                SimpleNamespace(
                    filename=f"{pack_code}-{effective_doc_type}-{suffix}.xlsx", payload=b"xlsx"
                )
            ]

        with mock.patch(
            "wms.views_print_docs.render_pack_document_xlsx_documents",
            side_effect=_render_side_effect,
        ):
            from wms.views_print_docs import _build_shipment_view_bundle_a4_xlsx_documents

            documents = _build_shipment_view_bundle_a4_xlsx_documents(shipment)

        self.assertEqual(
            [entry.filename for entry in documents],
            [
                "C-shipment_note-shipment.xlsx",
                "C-customs_note-shipment.xlsx",
                "B-packing_list_shipment-shipment.xlsx",
                "B-packing_list_shipment-shipment.xlsx",
            ],
        )

    def test_scan_shipment_view_bundle_pdf_routes_a4_bundle_to_pdf_builder(self):
        shipment = self._create_shipment()
        documents = [SimpleNamespace(filename="a4.xlsx", payload=b"xlsx-a4")]
        with (
            mock.patch(
                "wms.views_print_docs._build_shipment_view_bundle_a4_xlsx_documents",
                return_value=documents,
            ) as docs_mock,
            mock.patch(
                "wms.views_print_docs._build_pdf_response_from_xlsx_documents",
                return_value=HttpResponse("pdf-a4"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_bundle_pdf",
                    kwargs={"shipment_id": shipment.id, "bundle_key": "a4"},
                )
            )

        self.assertEqual(response.status_code, 200)
        docs_mock.assert_called_once_with(shipment)
        pdf_mock.assert_called_once_with(
            documents,
            filename=f"shipment-view-a4-{shipment.reference}.pdf",
            two_up_on_a4=False,
        )

    def test_scan_shipment_view_bundle_pdf_returns_helper_job_payload_for_a4_bundle(self):
        shipment = self._create_shipment()
        documents = [
            SimpleNamespace(filename="a4-1.xlsx", payload=b"xlsx-a4-1"),
            SimpleNamespace(filename="a4-2.xlsx", payload=b"xlsx-a4-2"),
        ]
        with mock.patch(
            "wms.views_print_docs._build_shipment_view_bundle_a4_xlsx_documents",
            return_value=documents,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_bundle_pdf",
                    kwargs={"shipment_id": shipment.id, "bundle_key": "a4"},
                ),
                {"helper": "1"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["output_filename"], f"shipment-view-a4-{shipment.reference}.pdf")
        self.assertTrue(payload["merge"])
        self.assertEqual(len(payload["documents"]), 2)
        self.assertIn("helper_document=0", payload["documents"][0]["download_url"])
        self.assertEqual(
            payload["required_capabilities"],
            ["pdf_render", "excel_render", "pdf_merge"],
        )

    def test_scan_shipment_view_bundle_pdf_returns_helper_document_when_requested(self):
        shipment = self._create_shipment()
        documents = [
            SimpleNamespace(filename="a4-1.xlsx", payload=b"xlsx-a4-1"),
            SimpleNamespace(filename="a4-2.xlsx", payload=b"xlsx-a4-2"),
        ]
        with mock.patch(
            "wms.views_print_docs._build_shipment_view_bundle_a4_xlsx_documents",
            return_value=documents,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_bundle_pdf",
                    kwargs={"shipment_id": shipment.id, "bundle_key": "a4"},
                ),
                {"helper_document": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(response.content, b"xlsx-a4-2")

    def test_scan_shipment_view_bundle_pdf_routes_a5_bundle_to_two_up_pdf_builder(self):
        shipment = self._create_shipment()
        documents = [SimpleNamespace(filename="a5.xlsx", payload=b"xlsx-a5")]
        with (
            mock.patch(
                "wms.views_print_docs._build_shipment_view_bundle_a5_xlsx_documents",
                return_value=documents,
            ) as docs_mock,
            mock.patch(
                "wms.views_print_docs._build_pdf_response_from_xlsx_documents",
                return_value=HttpResponse("pdf-a5"),
            ) as pdf_mock,
        ):
            response = self.client.get(
                reverse(
                    "scan:scan_shipment_view_bundle_pdf",
                    kwargs={"shipment_id": shipment.id, "bundle_key": "a5"},
                )
            )

        self.assertEqual(response.status_code, 200)
        docs_mock.assert_called_once_with(shipment)
        pdf_mock.assert_called_once_with(
            documents,
            filename=f"shipment-view-a5-{shipment.reference}.pdf",
            two_up_on_a4=True,
        )

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
                ),
                {"delivery": "pdf"},
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
                ),
                {"delivery": "pdf"},
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
                reverse("scan:scan_carton_document", kwargs={"carton_id": carton.id}),
                {"delivery": "pdf"},
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
        self.assertIsNone(context["item_rows"][0]["expires_on"])
        self.assertEqual(context["carton_weight_kg"], 1.0)
        self.assertTrue(context["hide_footer"])

    def test_scan_carton_document_fallback_context_prefers_manual_expiry(self):
        carton = self._create_standalone_carton_with_item()
        item = carton.cartonitem_set.get()
        item.display_expires_on = date(2026, 2, 1)
        item.save(update_fields=["display_expires_on"])

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
        context = render_mock.call_args.args[2]
        self.assertEqual(context["item_rows"][0]["expires_on"], date(2026, 2, 1))

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
