"""Scan views re-exported for URL routing."""

from .views_scan_account_validations import (
    scan_account_validation_detail,
    scan_account_validation_list,
    scan_contact_validations_hub,
    scan_recipient_validation_detail,
    scan_recipient_validation_list,
)
from .views_scan_admin import (
    scan_admin_carton_formats,
    scan_admin_contacts,
    scan_admin_product_create,
    scan_admin_product_detail,
    scan_admin_products,
    scan_admin_recipient_organization_detail,
    scan_contacts_roles,
    scan_product_labels,
    scan_product_labels_print_labels,
    scan_product_labels_print_qr,
)
from .views_scan_billing import (
    scan_billing_editor,
    scan_billing_equivalence,
    scan_billing_settings,
)
from .views_scan_dashboard import scan_dashboard, scan_root
from .views_scan_design import scan_admin_design
from .views_scan_misc import (
    scan_change_account,
    scan_faq,
    scan_logout,
    scan_service_worker,
    scan_ui_lab,
)
from .views_scan_orders import (
    scan_order,
    scan_order_detail,
    scan_orders_view,
    scan_preparateur_order_prepare,
    scan_preparateur_order_prepare_picking,
    scan_preparateur_order_select,
)
from .views_scan_pilotage import scan_pilotage
from .views_scan_preparateur import (
    scan_preparateur_home,
    scan_preparateur_pack_start,
    scan_preparateur_rangement,
)
from .views_scan_preparation import (
    scan_preparation_parameter_set_config,
    scan_preparation_run_create,
    scan_preparation_run_detail,
    scan_preparation_run_list,
)
from .views_scan_receipts import (
    scan_receipt_detail,
    scan_receipts_view,
    scan_receive,
    scan_receive_association,
    scan_receive_listing,
    scan_receive_listing_product_edit,
    scan_receive_pallet,
)
from .views_scan_settings import scan_settings
from .views_scan_shipments import (
    scan_carton_edit,
    scan_cartons_ready,
    scan_kits_view,
    scan_local_document_helper_installer,
    scan_pack,
    scan_preparateur_last_carton,
    scan_prepare_kits,
    scan_prepare_kits_picking,
    scan_shipment_batch_create,
    scan_shipment_batch_summary,
    scan_shipment_create,
    scan_shipment_edit,
    scan_shipment_track,
    scan_shipment_track_legacy,
    scan_shipments_ready,
    scan_shipments_tracking,
)
from .views_scan_stock import (
    scan_out,
    scan_recipient_needs,
    scan_stock,
    scan_stock_update,
    scan_sync,
)
from .views_shipment_tracking_access import (
    scan_shipment_tracking_access_login,
    scan_shipment_tracking_access_logout,
    scan_shipment_tracking_access_recovery,
    scan_shipment_tracking_access_set_password,
)

SCAN_FLOW_EXPORTS = (
    "scan_root",
    "scan_dashboard",
    "scan_pilotage",
    "scan_stock",
    "scan_recipient_needs",
    "scan_kits_view",
    "scan_local_document_helper_installer",
    "scan_cartons_ready",
    "scan_shipments_ready",
    "scan_preparation_run_list",
    "scan_preparation_run_create",
    "scan_preparation_parameter_set_config",
    "scan_preparation_run_detail",
    "scan_shipments_tracking",
    "scan_receipts_view",
    "scan_receipt_detail",
    "scan_stock_update",
    "scan_receive",
    "scan_receive_pallet",
    "scan_receive_listing",
    "scan_receive_listing_product_edit",
    "scan_receive_association",
    "scan_billing_settings",
    "scan_billing_equivalence",
    "scan_billing_editor",
    "scan_account_validation_list",
    "scan_account_validation_detail",
    "scan_contact_validations_hub",
    "scan_recipient_validation_list",
    "scan_recipient_validation_detail",
    "scan_order",
    "scan_order_detail",
    "scan_orders_view",
    "scan_preparateur_home",
    "scan_preparateur_order_select",
    "scan_preparateur_order_prepare",
    "scan_preparateur_order_prepare_picking",
    "scan_prepare_kits",
    "scan_prepare_kits_picking",
    "scan_preparateur_pack_start",
    "scan_preparateur_rangement",
    "scan_pack",
    "scan_preparateur_last_carton",
    "scan_carton_edit",
    "scan_shipment_create",
    "scan_shipment_batch_create",
    "scan_shipment_batch_summary",
    "scan_shipment_edit",
    "scan_shipment_track",
    "scan_shipment_tracking_access_login",
    "scan_shipment_tracking_access_recovery",
    "scan_shipment_tracking_access_set_password",
    "scan_shipment_tracking_access_logout",
    "scan_shipment_track_legacy",
    "scan_out",
    "scan_sync",
    "scan_admin_carton_formats",
    "scan_admin_contacts",
    "scan_contacts_roles",
    "scan_admin_recipient_organization_detail",
    "scan_admin_products",
    "scan_admin_product_create",
    "scan_admin_product_detail",
    "scan_product_labels",
    "scan_product_labels_print_labels",
    "scan_product_labels_print_qr",
    "scan_admin_design",
)

SCAN_MISC_EXPORTS = (
    "scan_change_account",
    "scan_faq",
    "scan_logout",
    "scan_ui_lab",
    "scan_settings",
    "scan_service_worker",
)

__all__ = [*SCAN_FLOW_EXPORTS, *SCAN_MISC_EXPORTS]
