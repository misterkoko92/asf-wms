"""Print views re-exported for URL routing."""

from .views_print_docs import (
    scan_carton_document,
    scan_carton_picking,
    scan_shipment_carton_document,
    scan_shipment_document,
    scan_shipment_document_delete,
    scan_shipment_document_upload,
)
from .views_print_labels import (
    scan_shipment_label,
    scan_shipment_labels,
)
from .views_print_templates import (
    scan_print_template_edit,
    scan_print_template_preview,
    scan_print_templates,
)

__all__ = [
    "scan_shipment_document",
    "scan_shipment_carton_document",
    "scan_carton_document",
    "scan_carton_picking",
    "scan_shipment_labels",
    "scan_shipment_label",
    "scan_print_templates",
    "scan_print_template_edit",
    "scan_print_template_preview",
    "scan_shipment_document_upload",
    "scan_shipment_document_delete",
]
