from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from openpyxl import Workbook

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    Carton,
    CartonItem,
    Destination,
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
    render_pack_xlsx_documents,
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

    def test_generate_pack_expands_destination_all_labels_per_carton(self):
        pack = PrintPack.objects.create(code="PD", name="Pack D")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="destination_label",
            variant="all_labels",
            sequence=1,
            enabled=True,
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        carton_one = Carton.objects.create(code="C-001", shipment=shipment)
        carton_two = Carton.objects.create(code="C-002", shipment=shipment)

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            side_effect=[b"xlsx-1", b"xlsx-2"],
        ) as render_mock, mock.patch(
            "wms.print_pack_engine.convert_excel_to_pdf_via_graph",
            side_effect=[b"%PDF-1", b"%PDF-2"],
        ), mock.patch(
            "wms.print_pack_engine.merge_pdf_documents",
            return_value=b"%PDF-merged",
        ) as merge_mock:
            artifact = generate_pack(pack_code="PD", shipment=shipment, user=self.user)

        self.assertEqual(render_mock.call_count, 2)
        first_kwargs = render_mock.call_args_list[0].kwargs
        second_kwargs = render_mock.call_args_list[1].kwargs
        self.assertEqual(first_kwargs["shipment"], shipment)
        self.assertEqual(second_kwargs["shipment"], shipment)
        self.assertEqual(first_kwargs["carton"], carton_one)
        self.assertEqual(second_kwargs["carton"], carton_two)
        self.assertEqual(artifact.items.count(), 2)
        merge_mock.assert_called_once_with([b"%PDF-1", b"%PDF-2"])

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

    def test_render_pack_xlsx_documents_expands_destination_all_labels_per_carton(self):
        pack = PrintPack.objects.create(code="PX", name="Pack X")
        PrintPackDocument.objects.create(
            pack=pack,
            doc_type="destination_label",
            variant="all_labels",
            sequence=1,
            enabled=True,
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        Carton.objects.create(code="C-001", shipment=shipment)
        Carton.objects.create(code="C-002", shipment=shipment)

        with mock.patch(
            "wms.print_pack_engine._render_document_xlsx_bytes",
            side_effect=[b"xlsx-1", b"xlsx-2"],
        ) as render_mock:
            documents = render_pack_xlsx_documents(
                pack_code="PX",
                shipment=shipment,
                variant="all_labels",
            )

        self.assertEqual(render_mock.call_count, 2)
        self.assertEqual(len(documents), 2)
        self.assertTrue(documents[0].filename.endswith("-1.xlsx"))
        self.assertTrue(documents[1].filename.endswith("-2.xlsx"))
        self.assertEqual(documents[0].payload, b"xlsx-1")
        self.assertEqual(documents[1].payload, b"xlsx-2")

    def test_render_pack_xlsx_documents_uses_seeded_templates_when_filefields_missing(
        self,
    ):
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )
        template_dir = Path(settings.BASE_DIR) / "data" / "print_templates"
        with override_settings(PRINT_PACK_TEMPLATE_DIRS=[str(template_dir)]):
            documents = render_pack_xlsx_documents(
                pack_code="C",
                shipment=shipment,
                variant="shipment",
            )

        self.assertEqual(len(documents), 2)
        self.assertTrue(documents[0].filename.startswith("C-shipment_note-"))
        self.assertTrue(documents[0].filename.endswith(".xlsx"))
        self.assertTrue(documents[1].filename.startswith("C-contact_label-"))
        self.assertTrue(documents[1].filename.endswith(".xlsx"))
        self.assertTrue(all(isinstance(entry.payload, bytes) for entry in documents))
        self.assertTrue(all(len(entry.payload) > 0 for entry in documents))

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
        self.assertEqual(payload["carton"]["position"], "")
        self.assertEqual(payload["document"]["doc_type"], "shipment_note")
        self.assertEqual(payload["document"]["variant"], "shipment")
        self.assertTrue(payload["document"]["generated_on"])

    def test_render_document_xlsx_bytes_raises_when_template_is_missing(self):
        document = SimpleNamespace(
            doc_type="shipment_note",
            xlsx_template_file=None,
        )
        with self.assertRaises(PrintPackEngineError):
            _render_document_xlsx_bytes(document=document)

    def test_render_document_xlsx_bytes_reads_template_from_search_dir_when_db_file_missing(
        self,
    ):
        pack = PrintPack.objects.create(code="TC", name="Template Canonical")
        document = PrintPackDocument.objects.create(
            pack=pack,
            doc_type="shipment_note",
            variant="shipment",
            sequence=1,
            enabled=True,
            xlsx_template_file=None,
        )
        with TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "TC__shipment_note__shipment.xlsx"
            workbook = Workbook()
            workbook.active["A1"] = "Template"
            workbook.save(template_path)
            workbook.close()

            with override_settings(PRINT_PACK_TEMPLATE_DIRS=[temp_dir]):
                rendered_bytes = _render_document_xlsx_bytes(document=document)

        self.assertIsInstance(rendered_bytes, bytes)
        self.assertGreater(len(rendered_bytes), 0)

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
        self.assertEqual(payload["carton"]["position"], 1)

    def test_build_mapping_payload_includes_recipient_contact_details(self):
        recipient = Contact.objects.create(
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            email="jean@example.org",
            email2="secours@example.org",
            phone="+33 1 23 45 67 89",
            phone2="+33 6 11 22 33 44",
            notes="Urgence: +223 70 00 00 00",
        )
        ContactAddress.objects.create(
            contact=recipient,
            is_default=True,
            address_line1="10 Rue du Test",
            postal_code="75010",
            city="Paris",
            country="France",
            phone="+33 9 00 00 00 00",
            email="adresse@example.org",
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper",
            recipient_name="Fallback Recipient",
            recipient_contact_ref=recipient,
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.user,
        )

        payload = _build_mapping_payload(shipment=shipment)

        recipient_payload = payload["shipment"]["recipient"]
        self.assertEqual(recipient_payload["title_name"], "M. Jean DUPONT")
        self.assertEqual(recipient_payload["postal_address"], "10 Rue du Test")
        self.assertEqual(recipient_payload["postal_code"], "75010")
        self.assertEqual(recipient_payload["city"], "Paris")
        self.assertEqual(recipient_payload["country"], "France")
        self.assertEqual(recipient_payload["phone_1"], "+33 1 23 45 67 89")
        self.assertEqual(recipient_payload["phone_2"], "+33 6 11 22 33 44")
        self.assertEqual(recipient_payload["phone_3"], "+33 9 00 00 00 00")
        self.assertEqual(recipient_payload["email_1"], "jean@example.org")
        self.assertEqual(recipient_payload["email_2"], "secours@example.org")
        self.assertEqual(recipient_payload["email_3"], "adresse@example.org")
        self.assertEqual(
            recipient_payload["emergency_contact"],
            "Urgence: +223 70 00 00 00",
        )
        self.assertEqual(
            recipient_payload["postal_address_full"],
            "10 Rue du Test, 75010 Paris, France",
        )
        self.assertEqual(
            recipient_payload["contact_primary"],
            "+33 1 23 45 67 89, jean@example.org",
        )

    def test_build_mapping_payload_includes_shipment_note_summary_and_party_contacts(self):
        warehouse = Warehouse.objects.create(name="W")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        hf_category = ProductCategory.objects.create(name="HF")
        mm_category = ProductCategory.objects.create(name="MM")
        hf_product = Product.objects.create(
            sku="SKU-HF-1",
            name="Hors format",
            brand="ASF",
            category=hf_category,
            weight_g=2000,
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )
        mm_product = Product.objects.create(
            sku="SKU-MM-1",
            name="Medical",
            brand="ASF",
            category=mm_category,
            weight_g=1500,
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )
        hf_lot = ProductLot.objects.create(
            product=hf_product,
            lot_code="LOT-HF",
            quantity_on_hand=20,
            location=location,
        )
        mm_lot = ProductLot.objects.create(
            product=mm_product,
            lot_code="LOT-MM",
            quantity_on_hand=20,
            location=location,
        )

        shipper_org = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name="MSF Paris",
        )
        shipper = Contact.objects.create(
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            organization=shipper_org,
            phone="+33 1 00 00 00 00",
            email="jean.dupont@example.org",
        )
        ContactAddress.objects.create(
            contact=shipper,
            is_default=True,
            address_line1="1 Rue de Paris",
            postal_code="75001",
            city="Paris",
            country="France",
        )

        recipient_org = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name="MSF Abidjan",
            phone="+225 1 11 11 11 11",
            email="abidjan@example.org",
        )
        ContactAddress.objects.create(
            contact=recipient_org,
            is_default=True,
            address_line1="10 Avenue Lagune",
            postal_code="01 BP 1000",
            city="Abidjan",
            country="Cote d'Ivoire",
        )

        correspondent_org = Contact.objects.create(
            contact_type=ContactType.ORGANIZATION,
            name="MSF Bamako",
            phone="+223 2 22 22 22 22",
            email="bamako@example.org",
        )
        ContactAddress.objects.create(
            contact=correspondent_org,
            is_default=True,
            address_line1="22 Rue Fleuve",
            postal_code="BP 500",
            city="Bamako",
            country="Mali",
        )

        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent_org,
            is_active=True,
        )
        shipment = Shipment.objects.create(
            shipper_name="Shipper Fallback",
            shipper_contact_ref=shipper,
            recipient_name="Recipient Fallback",
            recipient_contact_ref=recipient_org,
            correspondent_name="Correspondent Fallback",
            correspondent_contact_ref=correspondent_org,
            destination=destination,
            destination_address="Port d'Abidjan",
            destination_country="Cote d'Ivoire",
            created_by=self.user,
        )
        carton = Carton.objects.create(code="C-001", shipment=shipment)
        CartonItem.objects.create(carton=carton, product_lot=hf_lot, quantity=2)
        CartonItem.objects.create(carton=carton, product_lot=mm_lot, quantity=2)

        payload = _build_mapping_payload(shipment=shipment)

        shipment_payload = payload["shipment"]
        self.assertEqual(shipment_payload["origin_city"], "PARIS")
        self.assertEqual(shipment_payload["origin_iata"], "CDG")
        self.assertEqual(shipment_payload["destination_city"], "Abidjan")
        self.assertEqual(shipment_payload["destination_iata"], "ABJ")
        self.assertEqual(shipment_payload["total_weight_label"], "7 kg")
        self.assertEqual(shipment_payload["hors_format_total_count"], 2)

        self.assertEqual(shipment_payload["shipper"]["title_name"], "M. Jean DUPONT")
        self.assertEqual(shipment_payload["shipper"]["structure_name"], "MSF Paris")
        self.assertEqual(
            shipment_payload["shipper"]["postal_address_full"],
            "1 Rue de Paris, 75001 Paris, France",
        )
        self.assertEqual(
            shipment_payload["shipper"]["contact_primary"],
            "+33 1 00 00 00 00, jean.dupont@example.org",
        )

        self.assertEqual(shipment_payload["recipient"]["structure_name"], "MSF Abidjan")
        self.assertEqual(shipment_payload["recipient"]["title_name"], "MSF Abidjan")
        self.assertEqual(
            shipment_payload["recipient"]["contact_primary"],
            "+225 1 11 11 11 11, abidjan@example.org",
        )

        self.assertEqual(
            shipment_payload["correspondent"]["structure_name"],
            "MSF Bamako",
        )
        self.assertEqual(
            shipment_payload["correspondent"]["contact_primary"],
            "+223 2 22 22 22 22, bamako@example.org",
        )
