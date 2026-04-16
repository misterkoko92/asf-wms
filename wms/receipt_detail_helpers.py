from django.urls import reverse

from .models import ReceiptType


def _receipt_edit_url(receipt):
    if receipt.receipt_type == ReceiptType.ASSOCIATION:
        return f"{reverse('scan:scan_receive_association')}?receipt_id={receipt.id}"
    return f"{reverse('scan:scan_receive')}?receipt={receipt.id}"


def build_receipt_detail_payload(receipt):
    receipt_lines = list(receipt.lines.select_related("product", "location").all())
    hors_format_items = list(receipt.hors_format_items.all())
    shipment_allocations = list(receipt.shipment_allocations.select_related("shipment").all())
    return {
        "receipt": receipt,
        "receipt_lines": receipt_lines,
        "hors_format_items": hors_format_items,
        "shipment_allocations": shipment_allocations,
        "back_url": reverse("scan:scan_receipts_view"),
        "edit_url": _receipt_edit_url(receipt),
    }
