from django.test import SimpleTestCase


class ShipmentLogisticsPrintStrategyTests(SimpleTestCase):
    def test_shipment_logistics_strategy_matches_validated_policy(self):
        from wms.print_document_strategy import SHIPMENT_LOGISTICS_PRINT_STRATEGY

        donation_policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY["donation_certificate"]
        self.assertEqual(donation_policy["source_format"], "html")
        self.assertEqual(donation_policy["fidelity_tier"], "locked")
        self.assertEqual(donation_policy["internal_delivery"], "browser_print")
        self.assertTrue(donation_policy["external_pdf_required"])

        label_policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY["shipment_label"]
        self.assertIn(label_policy["source_format"], {"html", "svg"})
        self.assertEqual(label_policy["fidelity_tier"], "visual_identity")
        self.assertEqual(label_policy["internal_delivery"], "browser_print")
        self.assertFalse(label_policy["external_pdf_required"])

        expected_flexible_documents = {
            "packing_list_carton",
            "packing_list_shipment",
            "shipment_note",
            "customs",
            "contact_label",
        }
        for document_key in expected_flexible_documents:
            with self.subTest(document_key=document_key):
                policy = SHIPMENT_LOGISTICS_PRINT_STRATEGY[document_key]
                self.assertEqual(policy["source_format"], "html")
                self.assertEqual(policy["fidelity_tier"], "flexible")
                self.assertEqual(policy["internal_delivery"], "browser_print")
                self.assertTrue(policy["external_pdf_required"])
