from dataclasses import dataclass


@dataclass(frozen=True)
class PrintPackRequest:
    pack_code: str
    variant: str
    doc_type: str = ""


_DOCUMENT_TO_PACK = {
    "shipment_note": PrintPackRequest(
        pack_code="C",
        variant="shipment",
        doc_type="shipment_note",
    ),
    "packing_list_shipment": PrintPackRequest(
        pack_code="B",
        variant="shipment",
        doc_type="packing_list_shipment",
    ),
    "donation_certificate": PrintPackRequest(
        pack_code="B",
        variant="shipment",
        doc_type="donation_certificate",
    ),
}


def resolve_pack_request(doc_type):
    return _DOCUMENT_TO_PACK.get((doc_type or "").strip())


def resolve_carton_picking_pack():
    return PrintPackRequest(pack_code="A", variant="single_carton")


def resolve_shipment_labels_pack():
    return PrintPackRequest(pack_code="D", variant="all_labels")


def resolve_single_label_pack():
    return PrintPackRequest(pack_code="D", variant="single_label")


def resolve_carton_packing_pack():
    return PrintPackRequest(pack_code="B", variant="per_carton_single")
