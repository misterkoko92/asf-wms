"""Re-export views for URL routing and tests."""

from .services import receive_receipt_line, reserve_stock_for_order
from .views_imports import scan_import
from .views_portal import (
    portal_account,
    portal_account_request,
    portal_change_password,
    portal_dashboard,
    portal_login,
    portal_logout,
    portal_order_create,
    portal_order_detail,
    portal_recipients,
    portal_set_password,
)
from .views_print import (
    scan_carton_document,
    scan_carton_picking,
    scan_print_template_edit,
    scan_print_template_preview,
    scan_print_templates,
    scan_shipment_carton_document,
    scan_shipment_document,
    scan_shipment_document_delete,
    scan_shipment_document_upload,
    scan_shipment_label,
    scan_shipment_labels,
)
from .views_public import (
    scan_public_account_request,
    scan_public_order,
    scan_public_order_summary,
)
from .views_scan import (
    scan_cartons_ready,
    scan_faq,
    scan_order,
    scan_orders_view,
    scan_out,
    scan_pack,
    scan_receive,
    scan_receive_association,
    scan_receive_pallet,
    scan_receipts_view,
    scan_service_worker,
    scan_shipment_create,
    scan_shipment_edit,
    scan_shipment_track,
    scan_shipment_track_legacy,
    scan_shipments_ready,
    scan_stock,
    scan_stock_update,
    scan_sync,
)

PORTAL_EXPORTS = (
    "portal_login",
    "portal_logout",
    "portal_set_password",
    "portal_change_password",
    "portal_dashboard",
    "portal_order_create",
    "portal_order_detail",
    "portal_recipients",
    "portal_account",
    "portal_account_request",
)

PUBLIC_EXPORTS = (
    "scan_public_order_summary",
    "scan_public_account_request",
    "scan_public_order",
)

SCAN_FLOW_EXPORTS = (
    "scan_stock",
    "scan_cartons_ready",
    "scan_shipments_ready",
    "scan_receipts_view",
    "scan_stock_update",
    "scan_receive",
    "scan_receive_pallet",
    "scan_receive_association",
    "scan_order",
    "scan_orders_view",
    "scan_pack",
    "scan_shipment_create",
    "scan_shipment_edit",
    "scan_shipment_track",
    "scan_shipment_track_legacy",
)

PRINT_EXPORTS = (
    "scan_shipment_document",
    "scan_shipment_carton_document",
    "scan_carton_document",
    "scan_carton_picking",
    "scan_shipment_labels",
    "scan_shipment_label",
    "scan_print_templates",
    "scan_print_template_edit",
    "scan_print_template_preview",
)

IMPORT_EXPORTS = ("scan_import",)

SCAN_MISC_EXPORTS = (
    "scan_shipment_document_upload",
    "scan_shipment_document_delete",
    "scan_out",
    "scan_sync",
    "scan_faq",
    "scan_service_worker",
)

SERVICE_EXPORTS = ("receive_receipt_line", "reserve_stock_for_order")

__all__ = [
    *PORTAL_EXPORTS,
    *PUBLIC_EXPORTS,
    *SCAN_FLOW_EXPORTS,
    *PRINT_EXPORTS,
    *IMPORT_EXPORTS,
    *SCAN_MISC_EXPORTS,
    *SERVICE_EXPORTS,
]
