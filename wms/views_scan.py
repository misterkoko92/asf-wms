"""Scan views re-exported for URL routing."""

from .views_scan_dashboard import scan_dashboard
from .views_scan_admin import scan_admin_contacts, scan_admin_products
from .views_scan_misc import scan_faq, scan_service_worker, scan_ui_lab
from .views_scan_orders import scan_order, scan_orders_view
from .views_scan_receipts import (
    scan_receive,
    scan_receive_association,
    scan_receive_pallet,
    scan_receipts_view,
)
from .views_scan_settings import scan_settings
from .views_scan_shipments import (
    scan_cartons_ready,
    scan_kits_view,
    scan_pack,
    scan_prepare_kits,
    scan_prepare_kits_picking,
    scan_shipment_create,
    scan_shipment_edit,
    scan_shipment_track,
    scan_shipment_track_legacy,
    scan_shipments_tracking,
    scan_shipments_ready,
)
from .views_scan_stock import scan_out, scan_stock, scan_stock_update, scan_sync

SCAN_FLOW_EXPORTS = (
    "scan_dashboard",
    "scan_stock",
    "scan_kits_view",
    "scan_cartons_ready",
    "scan_shipments_ready",
    "scan_shipments_tracking",
    "scan_receipts_view",
    "scan_stock_update",
    "scan_receive",
    "scan_receive_pallet",
    "scan_receive_association",
    "scan_order",
    "scan_orders_view",
    "scan_prepare_kits",
    "scan_prepare_kits_picking",
    "scan_pack",
    "scan_shipment_create",
    "scan_shipment_edit",
    "scan_shipment_track",
    "scan_shipment_track_legacy",
    "scan_out",
    "scan_sync",
    "scan_admin_contacts",
    "scan_admin_products",
)

SCAN_MISC_EXPORTS = (
    "scan_faq",
    "scan_ui_lab",
    "scan_settings",
    "scan_service_worker",
)

__all__ = [*SCAN_FLOW_EXPORTS, *SCAN_MISC_EXPORTS]
