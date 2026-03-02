from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    GeneratedPrintArtifact,
    GeneratedPrintArtifactItem,
    PrintCellMapping,
    PrintPack,
    PrintPackDocument,
)


class PrintPackModelTests(TestCase):
    def test_default_pack_configuration_is_seeded(self):
        expected_packs = {
            "A": ("A4", ""),
            "B": ("A5", "A4"),
            "C": ("A5", "A4"),
            "D": ("A5", ""),
        }
        for code, (default_format, fallback_format) in expected_packs.items():
            pack = PrintPack.objects.get(code=code)
            self.assertEqual(pack.default_page_format, default_format)
            self.assertEqual(pack.fallback_page_format or "", fallback_format)
            self.assertTrue(pack.active)

        expected_documents = {
            ("A", "picking", "single_carton", 1),
            ("B", "packing_list_shipment", "shipment", 1),
            ("B", "donation_certificate", "shipment", 2),
            ("B", "packing_list_carton", "per_carton_single", 1),
            ("C", "shipment_note", "shipment", 1),
            ("C", "contact_label", "shipment", 2),
            ("D", "destination_label", "all_labels", 1),
            ("D", "destination_label", "single_label", 1),
        }
        seeded_documents = set(
            PrintPackDocument.objects.values_list(
                "pack__code",
                "doc_type",
                "variant",
                "sequence",
            )
        )
        self.assertTrue(expected_documents.issubset(seeded_documents))

    def test_pack_models_store_mapping_and_artifact_status(self):
        user = get_user_model().objects.create_user(
            username="printpack-admin",
            password="x",
        )
        pack = PrintPack.objects.create(
            code="PM",
            name="Pack B",
            active=True,
            default_page_format="A5",
            fallback_page_format="A4",
        )
        pack_document = PrintPackDocument.objects.create(
            pack=pack,
            doc_type="packing_list_shipment",
            variant="shipment",
            sequence=1,
            enabled=True,
        )
        mapping = PrintCellMapping.objects.create(
            pack_document=pack_document,
            worksheet_name="Main",
            cell_ref="D5",
            source_key="shipment.recipient.full_name",
            transform="upper",
            required=True,
        )
        artifact = GeneratedPrintArtifact.objects.create(
            pack_code=pack.code,
            status="sync_pending",
            created_by=user,
        )
        item = GeneratedPrintArtifactItem.objects.create(
            artifact=artifact,
            doc_type=pack_document.doc_type,
            variant=pack_document.variant,
            sequence=pack_document.sequence,
        )

        self.assertEqual(pack_document.pack.code, "PM")
        self.assertEqual(mapping.cell_ref, "D5")
        self.assertEqual(artifact.status, "sync_pending")
        self.assertEqual(item.doc_type, "packing_list_shipment")

    def test_seeded_pack_mappings_match_current_cell_references(self):
        picking_doc = PrintPackDocument.objects.get(
            pack__code="A",
            doc_type="picking",
            variant="single_carton",
        )
        picking_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=picking_doc)
        }
        self.assertEqual(picking_mappings["A11"].source_key, "carton.code")
        self.assertEqual(picking_mappings["B11"].source_key, "carton.position")
        self.assertFalse(picking_mappings["B11"].required)
        self.assertEqual(
            picking_mappings["C11"].source_key,
            "shipment.carton_total_count",
        )
        self.assertEqual(picking_mappings["D11"].source_key, "shipment.reference")

        contact_label_doc = PrintPackDocument.objects.get(
            pack__code="C",
            doc_type="contact_label",
            variant="shipment",
        )
        contact_label_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=contact_label_doc)
        }
        self.assertEqual(contact_label_mappings["A5"].source_key, "shipment.shipper.title")
        self.assertEqual(
            contact_label_mappings["A6"].source_key,
            "shipment.shipper.first_name",
        )
        self.assertEqual(
            contact_label_mappings["A7"].source_key,
            "shipment.shipper.last_name",
        )
        self.assertEqual(
            contact_label_mappings["B5"].source_key,
            "shipment.shipper.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["C5"].source_key,
            "shipment.shipper.postal_address",
        )
        self.assertEqual(
            contact_label_mappings["C6"].source_key,
            "shipment.shipper.postal_code_city",
        )
        self.assertEqual(contact_label_mappings["C7"].source_key, "shipment.shipper.country")
        self.assertEqual(contact_label_mappings["D5"].source_key, "shipment.shipper.phone_1")
        self.assertEqual(contact_label_mappings["D6"].source_key, "shipment.shipper.email_1")
        self.assertEqual(
            contact_label_mappings["A12"].source_key,
            "shipment.recipient.title",
        )
        self.assertEqual(
            contact_label_mappings["A13"].source_key,
            "shipment.recipient.first_name",
        )
        self.assertEqual(
            contact_label_mappings["A14"].source_key,
            "shipment.recipient.last_name",
        )
        self.assertEqual(
            contact_label_mappings["B12"].source_key,
            "shipment.recipient.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["C12"].source_key,
            "shipment.recipient.postal_address",
        )
        self.assertEqual(
            contact_label_mappings["C13"].source_key,
            "shipment.recipient.postal_code_city",
        )
        self.assertEqual(
            contact_label_mappings["C14"].source_key,
            "shipment.recipient.country",
        )
        self.assertEqual(
            contact_label_mappings["D12"].source_key,
            "shipment.recipient.phone_1",
        )
        self.assertEqual(
            contact_label_mappings["D13"].source_key,
            "shipment.recipient.email_1",
        )
        self.assertEqual(
            contact_label_mappings["A19"].source_key,
            "shipment.correspondent.title",
        )
        self.assertEqual(
            contact_label_mappings["A20"].source_key,
            "shipment.correspondent.first_name",
        )
        self.assertEqual(
            contact_label_mappings["A21"].source_key,
            "shipment.correspondent.last_name",
        )
        self.assertEqual(
            contact_label_mappings["B19"].source_key,
            "shipment.correspondent.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["C19"].source_key,
            "shipment.correspondent.postal_address",
        )
        self.assertEqual(
            contact_label_mappings["C20"].source_key,
            "shipment.correspondent.postal_code_city",
        )
        self.assertEqual(
            contact_label_mappings["C21"].source_key,
            "shipment.correspondent.country",
        )
        self.assertEqual(
            contact_label_mappings["D19"].source_key,
            "shipment.correspondent.phone_1",
        )
        self.assertEqual(
            contact_label_mappings["D20"].source_key,
            "shipment.correspondent.email_1",
        )

        shipment_note_doc = PrintPackDocument.objects.get(
            pack__code="C",
            doc_type="shipment_note",
            variant="shipment",
        )
        shipment_note_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=shipment_note_doc)
        }
        self.assertEqual(shipment_note_mappings["A24"].source_key, "shipment.shipper.title")
        self.assertEqual(
            shipment_note_mappings["A25"].source_key,
            "shipment.shipper.first_name",
        )
        self.assertEqual(
            shipment_note_mappings["A26"].source_key,
            "shipment.shipper.last_name",
        )
        self.assertEqual(
            shipment_note_mappings["B24"].source_key,
            "shipment.shipper.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["C24"].source_key,
            "shipment.shipper.postal_address",
        )
        self.assertEqual(
            shipment_note_mappings["C25"].source_key,
            "shipment.shipper.postal_code_city",
        )
        self.assertEqual(shipment_note_mappings["C26"].source_key, "shipment.shipper.country")
        self.assertEqual(shipment_note_mappings["D24"].source_key, "shipment.shipper.phone_1")
        self.assertEqual(shipment_note_mappings["D25"].source_key, "shipment.shipper.email_1")
        self.assertEqual(
            shipment_note_mappings["A31"].source_key,
            "shipment.recipient.title",
        )
        self.assertEqual(
            shipment_note_mappings["A32"].source_key,
            "shipment.recipient.first_name",
        )
        self.assertEqual(
            shipment_note_mappings["A33"].source_key,
            "shipment.recipient.last_name",
        )
        self.assertEqual(
            shipment_note_mappings["B31"].source_key,
            "shipment.recipient.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["C31"].source_key,
            "shipment.recipient.postal_address",
        )
        self.assertEqual(
            shipment_note_mappings["C32"].source_key,
            "shipment.recipient.postal_code_city",
        )
        self.assertEqual(
            shipment_note_mappings["C33"].source_key,
            "shipment.recipient.country",
        )
        self.assertEqual(
            shipment_note_mappings["D31"].source_key,
            "shipment.recipient.phone_1",
        )
        self.assertEqual(
            shipment_note_mappings["D32"].source_key,
            "shipment.recipient.email_1",
        )
        self.assertEqual(
            shipment_note_mappings["A38"].source_key,
            "shipment.correspondent.title",
        )
        self.assertEqual(
            shipment_note_mappings["A39"].source_key,
            "shipment.correspondent.first_name",
        )
        self.assertEqual(
            shipment_note_mappings["A40"].source_key,
            "shipment.correspondent.last_name",
        )
        self.assertEqual(
            shipment_note_mappings["B38"].source_key,
            "shipment.correspondent.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["C38"].source_key,
            "shipment.correspondent.postal_address",
        )
        self.assertEqual(
            shipment_note_mappings["C39"].source_key,
            "shipment.correspondent.postal_code_city",
        )
        self.assertEqual(
            shipment_note_mappings["C40"].source_key,
            "shipment.correspondent.country",
        )
        self.assertEqual(
            shipment_note_mappings["D38"].source_key,
            "shipment.correspondent.phone_1",
        )
        self.assertEqual(
            shipment_note_mappings["D39"].source_key,
            "shipment.correspondent.email_1",
        )
