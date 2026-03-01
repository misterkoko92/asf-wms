from django.test import SimpleTestCase

from wms.print_pack_routing import (
    resolve_carton_packing_pack,
    resolve_carton_picking_pack,
    resolve_pack_request,
    resolve_shipment_labels_pack,
    resolve_single_label_pack,
)


class PrintPackRoutingTests(SimpleTestCase):
    def test_resolve_pack_request_maps_document_types_to_expected_pack(self):
        shipment_note = resolve_pack_request("shipment_note")
        packing_list = resolve_pack_request("packing_list_shipment")
        donation = resolve_pack_request("donation_certificate")
        unknown = resolve_pack_request("unknown_doc_type")

        self.assertEqual(shipment_note.pack_code, "C")
        self.assertEqual(shipment_note.variant, "shipment")
        self.assertEqual(packing_list.pack_code, "B")
        self.assertEqual(donation.pack_code, "B")
        self.assertIsNone(unknown)

    def test_resolve_non_document_routes_to_pack_variants(self):
        self.assertEqual(resolve_carton_picking_pack().pack_code, "A")
        self.assertEqual(resolve_carton_picking_pack().variant, "single_carton")
        self.assertEqual(resolve_shipment_labels_pack().pack_code, "D")
        self.assertEqual(resolve_shipment_labels_pack().variant, "all_labels")
        self.assertEqual(resolve_single_label_pack().variant, "single_label")
        self.assertEqual(resolve_carton_packing_pack().variant, "per_carton_single")
