from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    Carton,
    CartonItem,
    GeneratedPrintArtifactStatus,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    PrintPack,
    PrintPackDocument,
    Shipment,
    Warehouse,
)
from wms.print_pack_engine import (
    PrintPackEngineError,
    _build_mapping_payload,
    _render_document_xlsx_bytes,
    generate_pack,
)


class PrintPackEngineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="print-engine-user",
            password="pass1234",
        )

    def test_generate_pack_creates_single_document_artifact_without_merge(self):
        pack = PrintPack.objects.create(code="PA", name="Pack A")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="picking",
            variant="single_carton",
            sequence=1,
            enabled=True,
        )

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            return_value=b"xlsx-data",
        ) as render_mock, mock.patch(
            "wms.print_pack_engine.convert_excel_to_pdf_via_graph",
            return_value=b"%PDF-single",
        ) as convert_mock, mock.patch(
            "wms.print_pack_engine.merge_pdf_documents"
        ) as merge_mock:
            artifact = generate_pack(pack_code="PA", user=self.user)

        self.assertEqual(artifact.pack_code, "PA")
        self.assertEqual(artifact.status, GeneratedPrintArtifactStatus.SYNC_PENDING)
        self.assertEqual(artifact.items.count(), 1)
        render_mock.assert_called_once()
        convert_mock.assert_called_once()
        merge_mock.assert_not_called()

    def test_generate_pack_merges_when_multiple_documents_are_present(self):
        pack = PrintPack.objects.create(code="PB", name="Pack B")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="packing_list_shipment",
            variant="shipment",
            sequence=1,
            enabled=True,
        )
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="donation_certificate",
            variant="shipment",
            sequence=2,
            enabled=True,
        )

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            side_effect=[b"xlsx-1", b"xlsx-2"],
        ), mock.patch(
            "wms.print_pack_engine.convert_excel_to_pdf_via_graph",
            side_effect=[b"%PDF-1", b"%PDF-2"],
        ), mock.patch(
            "wms.print_pack_engine.merge_pdf_documents",
            return_value=b"%PDF-merged",
        ) as merge_mock:
            artifact = generate_pack(pack_code="PB", user=self.user)

        self.assertEqual(artifact.items.count(), 2)
        merge_mock.assert_called_once_with([b"%PDF-1", b"%PDF-2"])
        self.assertTrue(artifact.pdf_file.name.endswith(".pdf"))

    def test_generate_pack_raises_when_pack_is_unknown(self):
        with self.assertRaises(PrintPackEngineError):
            generate_pack(pack_code="Z", user=self.user)

    def test_generate_pack_raises_when_variant_filters_out_all_documents(self):
        pack = PrintPack.objects.create(code="PC", name="Pack C")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="shipment_note",
            variant="shipment",
            sequence=1,
            enabled=True,
        )

        with self.assertRaises(PrintPackEngineError):
            generate_pack(pack_code="PC", variant="single_carton", user=self.user)

    def test_build_mapping_payload_includes_shipment_and_carton_fields(self):
        shipment = SimpleNamespace(
            id=42,
            reference="260042",
            shipper_name="ASF Hub",
            recipient_name="CHU Nord",
            correspondent_name="M. Dupont",
            destination_address="1 Rue Test",
            destination_country="France",
            requested_delivery_date=None,
            notes="Fragile",
        )
        carton = SimpleNamespace(id=9, code="CARTON-9")
        document = SimpleNamespace(doc_type="shipment_note", variant="shipment")

        payload = _build_mapping_payload(
            shipment=shipment,
            carton=carton,
            document=document,
        )

        self.assertEqual(payload["shipment"]["reference"], "260042")
        self.assertEqual(payload["shipment"]["recipient"]["full_name"], "CHU Nord")
        self.assertEqual(payload["carton"]["code"], "CARTON-9")
        self.assertEqual(
            payload["document"],
            {"doc_type": "shipment_note", "variant": "shipment"},
        )

    def test_render_document_xlsx_bytes_raises_when_template_is_missing(self):
        document = SimpleNamespace(
            doc_type="shipment_note",
            xlsx_template_file=None,
        )
        with self.assertRaises(PrintPackEngineError):
            _render_document_xlsx_bytes(document=document)

    def test_build_mapping_payload_includes_shipment_item_position_and_root_category(self):
        warehouse = Warehouse.objects.create(name="W")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        root_category = ProductCategory.objects.create(name="MM")
        sub_category = ProductCategory.objects.create(name="Sub", parent=root_category)
        product = Product.objects.create(
            sku="SKU-PAYLOAD-1",
            name="Produit",
            brand="ASF",
            category=sub_category,
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )
        lot = ProductLot.objects.create(
            product=product,
            lot_code="LOT-PAYLOAD",
            quantity_on_hand=10,
            location=location,
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        carton = Carton.objects.create(code="C-001", shipment=shipment)
        CartonItem.objects.create(carton=carton, product_lot=lot, quantity=6)

        payload = _build_mapping_payload(shipment=shipment, carton=carton)

        self.assertEqual(payload["shipment"]["items"][0]["carton_position"], 1)
        self.assertEqual(payload["shipment"]["items"][0]["category_root"], "MM")
        self.assertEqual(payload["carton"]["items"][0]["category_root"], "MM")
