from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

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

        packing_carton_doc = PrintPackDocument.objects.get(
            pack__code="B",
            doc_type="packing_list_carton",
            variant="per_carton_single",
        )
        packing_carton_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=packing_carton_doc)
        }
        self.assertEqual(packing_carton_mappings["B9"].source_key, "carton.code")
        self.assertTrue(packing_carton_mappings["B9"].required)
        self.assertEqual(
            packing_carton_mappings["B12"].source_key,
            "carton.items[].product_name",
        )

        contact_label_doc = PrintPackDocument.objects.get(
            pack__code="C",
            doc_type="contact_label",
            variant="shipment",
        )
        contact_label_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=contact_label_doc)
        }
        self.assertEqual(len(contact_label_mappings), 15)
        self.assertEqual(contact_label_mappings["B3"].source_key, "shipment.shipper.display_name")
        self.assertEqual(
            contact_label_mappings["B4"].source_key,
            "shipment.shipper.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["B5"].source_key,
            "shipment.shipper.postal_address_display",
        )
        self.assertEqual(contact_label_mappings["B6"].source_key, "shipment.shipper.email_1")
        self.assertEqual(contact_label_mappings["B7"].source_key, "shipment.shipper.phone_1")
        self.assertEqual(
            contact_label_mappings["B10"].source_key,
            "shipment.recipient.display_name",
        )
        self.assertEqual(
            contact_label_mappings["B11"].source_key,
            "shipment.recipient.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["B12"].source_key,
            "shipment.recipient.postal_address_display",
        )
        self.assertEqual(contact_label_mappings["B13"].source_key, "shipment.recipient.email_1")
        self.assertEqual(contact_label_mappings["B14"].source_key, "shipment.recipient.phone_1")
        self.assertEqual(
            contact_label_mappings["B17"].source_key,
            "shipment.correspondent.display_name",
        )
        self.assertEqual(
            contact_label_mappings["B18"].source_key,
            "shipment.correspondent.structure_name",
        )
        self.assertEqual(
            contact_label_mappings["B19"].source_key,
            "shipment.correspondent.postal_address_display",
        )
        self.assertEqual(contact_label_mappings["B20"].source_key, "shipment.correspondent.email_1")
        self.assertEqual(contact_label_mappings["B21"].source_key, "shipment.correspondent.phone_1")
        self.assertEqual(contact_label_mappings["B3"].transform, "upper")
        self.assertEqual(contact_label_mappings["B5"].transform, "upper")
        self.assertEqual(contact_label_mappings["B6"].transform, "upper")
        self.assertEqual(contact_label_mappings["B10"].transform, "upper")
        self.assertEqual(contact_label_mappings["B19"].transform, "upper")

        shipment_note_doc = PrintPackDocument.objects.get(
            pack__code="C",
            doc_type="shipment_note",
            variant="shipment",
        )
        shipment_note_mappings = {
            mapping.cell_ref: mapping
            for mapping in PrintCellMapping.objects.filter(pack_document=shipment_note_doc)
        }
        self.assertEqual(len(shipment_note_mappings), 22)
        self.assertEqual(shipment_note_mappings["B7"].source_key, "shipment.origin_city")
        self.assertEqual(shipment_note_mappings["D7"].source_key, "shipment.destination_city")
        self.assertEqual(shipment_note_mappings["B8"].source_key, "shipment.origin_iata")
        self.assertEqual(shipment_note_mappings["D8"].source_key, "shipment.destination_iata")
        self.assertEqual(shipment_note_mappings["B10"].source_key, "shipment.reference")
        self.assertEqual(shipment_note_mappings["B11"].source_key, "shipment.total_weight_label")
        self.assertEqual(shipment_note_mappings["B12"].source_key, "shipment.carton_total_count")
        self.assertEqual(
            shipment_note_mappings["B18"].source_key,
            "shipment.shipper.display_name",
        )
        self.assertEqual(
            shipment_note_mappings["B19"].source_key,
            "shipment.shipper.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["B20"].source_key,
            "shipment.shipper.postal_address_display",
        )
        self.assertEqual(shipment_note_mappings["B21"].source_key, "shipment.shipper.email_1")
        self.assertEqual(shipment_note_mappings["B22"].source_key, "shipment.shipper.phone_1")
        self.assertEqual(
            shipment_note_mappings["B25"].source_key,
            "shipment.recipient.display_name",
        )
        self.assertEqual(
            shipment_note_mappings["B26"].source_key,
            "shipment.recipient.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["B27"].source_key,
            "shipment.recipient.postal_address_display",
        )
        self.assertEqual(shipment_note_mappings["B28"].source_key, "shipment.recipient.email_1")
        self.assertEqual(shipment_note_mappings["B29"].source_key, "shipment.recipient.phone_1")
        self.assertEqual(
            shipment_note_mappings["B32"].source_key,
            "shipment.correspondent.display_name",
        )
        self.assertEqual(
            shipment_note_mappings["B33"].source_key,
            "shipment.correspondent.structure_name",
        )
        self.assertEqual(
            shipment_note_mappings["B34"].source_key,
            "shipment.correspondent.postal_address_display",
        )
        self.assertEqual(shipment_note_mappings["B35"].source_key, "shipment.correspondent.email_1")
        self.assertEqual(shipment_note_mappings["B36"].source_key, "shipment.correspondent.phone_1")
        self.assertEqual(shipment_note_mappings["B18"].transform, "upper")
        self.assertEqual(shipment_note_mappings["B20"].transform, "upper")
        self.assertEqual(shipment_note_mappings["B21"].transform, "upper")
        self.assertEqual(shipment_note_mappings["B28"].transform, "upper")


class PrintPackMigrationTests(TransactionTestCase):
    migrate_from = ("wms", "0115_publicaccountrequest_destination_and_more")
    migrate_to = ("wms", "0116_fix_pack_b_packing_list_carton_mapping")

    def test_fix_pack_b_packing_list_carton_mapping_moves_carton_code_to_b9(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        old_pack_document_model = old_apps.get_model("wms", "PrintPackDocument")
        old_print_cell_mapping_model = old_apps.get_model("wms", "PrintCellMapping")
        old_pack_document = old_pack_document_model.objects.get(
            pack__code="B",
            doc_type="packing_list_carton",
            variant="per_carton_single",
        )
        self.assertTrue(
            old_print_cell_mapping_model.objects.filter(
                pack_document=old_pack_document,
                worksheet_name="Feuil1",
                cell_ref="B10",
                source_key="carton.code",
            ).exists()
        )
        self.assertFalse(
            old_print_cell_mapping_model.objects.filter(
                pack_document=old_pack_document,
                worksheet_name="Feuil1",
                cell_ref="B9",
                source_key="carton.code",
            ).exists()
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps

        new_pack_document_model = new_apps.get_model("wms", "PrintPackDocument")
        new_print_cell_mapping_model = new_apps.get_model("wms", "PrintCellMapping")
        new_pack_document = new_pack_document_model.objects.get(
            pack__code="B",
            doc_type="packing_list_carton",
            variant="per_carton_single",
        )
        self.assertTrue(
            new_print_cell_mapping_model.objects.filter(
                pack_document=new_pack_document,
                worksheet_name="Feuil1",
                cell_ref="B9",
                source_key="carton.code",
                required=True,
            ).exists()
        )
        self.assertFalse(
            new_print_cell_mapping_model.objects.filter(
                pack_document=new_pack_document,
                worksheet_name="Feuil1",
                cell_ref="B10",
                source_key="carton.code",
            ).exists()
        )
