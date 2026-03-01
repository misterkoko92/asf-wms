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
