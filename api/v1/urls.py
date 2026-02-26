from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    IntegrationDestinationViewSet,
    IntegrationEventViewSet,
    IntegrationShipmentViewSet,
    OrderViewSet,
    PackCartonView,
    ProductViewSet,
    ReceiveStockView,
)
from .ui_views import (
    UiCartonsView,
    UiPortalAccountView,
    UiDashboardView,
    UiOrderCreateShipmentView,
    UiOrderReviewStatusView,
    UiOrdersView,
    UiReceiptsView,
    UiScanOrderCreateView,
    UiScanOrderLineCreateView,
    UiScanOrderPrepareView,
    UiScanOrderStateView,
    UiPrintTemplateDetailView,
    UiPrintTemplatesView,
    UiPortalDashboardView,
    UiPortalOrderDetailView,
    UiPortalOrdersView,
    UiPortalRecipientDetailView,
    UiPortalRecipientsView,
    UiShipmentCloseView,
    UiShipmentCreateView,
    UiShipmentDocumentDetailView,
    UiShipmentDocumentsView,
    UiShipmentFormOptionsView,
    UiShipmentLabelDetailView,
    UiShipmentLabelsView,
    UiShipmentsReadyView,
    UiShipmentsReadyArchiveView,
    UiShipmentsTrackingView,
    UiShipmentTrackingEventCreateView,
    UiShipmentUpdateView,
    UiStockOutView,
    UiStockUpdateView,
    UiStockView,
)

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")
router.register("integrations/shipments", IntegrationShipmentViewSet, basename="integration-shipments")
router.register(
    "integrations/destinations",
    IntegrationDestinationViewSet,
    basename="integration-destinations",
)
router.register("integrations/events", IntegrationEventViewSet, basename="integration-events")

urlpatterns = [
    path("stock/receive/", ReceiveStockView.as_view(), name="stock-receive"),
    path("pack/", PackCartonView.as_view(), name="pack"),
    path("ui/dashboard/", UiDashboardView.as_view(), name="ui-dashboard"),
    path("ui/receipts/", UiReceiptsView.as_view(), name="ui-receipts"),
    path("ui/order/", UiScanOrderStateView.as_view(), name="ui-order-state"),
    path("ui/order/create/", UiScanOrderCreateView.as_view(), name="ui-order-create"),
    path("ui/order/lines/", UiScanOrderLineCreateView.as_view(), name="ui-order-line-create"),
    path("ui/order/prepare/", UiScanOrderPrepareView.as_view(), name="ui-order-prepare"),
    path("ui/orders/", UiOrdersView.as_view(), name="ui-orders"),
    path(
        "ui/orders/<int:order_id>/review-status/",
        UiOrderReviewStatusView.as_view(),
        name="ui-order-review-status",
    ),
    path(
        "ui/orders/<int:order_id>/create-shipment/",
        UiOrderCreateShipmentView.as_view(),
        name="ui-order-create-shipment",
    ),
    path("ui/cartons/", UiCartonsView.as_view(), name="ui-cartons"),
    path("ui/stock/", UiStockView.as_view(), name="ui-stock"),
    path("ui/stock/update/", UiStockUpdateView.as_view(), name="ui-stock-update"),
    path("ui/stock/out/", UiStockOutView.as_view(), name="ui-stock-out"),
    path(
        "ui/shipments/form-options/",
        UiShipmentFormOptionsView.as_view(),
        name="ui-shipment-form-options",
    ),
    path(
        "ui/shipments/ready/",
        UiShipmentsReadyView.as_view(),
        name="ui-shipments-ready",
    ),
    path(
        "ui/shipments/ready/archive-stale-drafts/",
        UiShipmentsReadyArchiveView.as_view(),
        name="ui-shipments-ready-archive-stale-drafts",
    ),
    path(
        "ui/shipments/tracking/",
        UiShipmentsTrackingView.as_view(),
        name="ui-shipments-tracking",
    ),
    path("ui/shipments/", UiShipmentCreateView.as_view(), name="ui-shipments-create"),
    path(
        "ui/shipments/<int:shipment_id>/",
        UiShipmentUpdateView.as_view(),
        name="ui-shipments-update",
    ),
    path(
        "ui/shipments/<int:shipment_id>/tracking-events/",
        UiShipmentTrackingEventCreateView.as_view(),
        name="ui-shipments-tracking-events-create",
    ),
    path(
        "ui/shipments/<int:shipment_id>/close/",
        UiShipmentCloseView.as_view(),
        name="ui-shipments-close",
    ),
    path(
        "ui/shipments/<int:shipment_id>/documents/",
        UiShipmentDocumentsView.as_view(),
        name="ui-shipments-documents",
    ),
    path(
        "ui/shipments/<int:shipment_id>/documents/<int:document_id>/",
        UiShipmentDocumentDetailView.as_view(),
        name="ui-shipments-document-detail",
    ),
    path(
        "ui/shipments/<int:shipment_id>/labels/",
        UiShipmentLabelsView.as_view(),
        name="ui-shipments-labels",
    ),
    path(
        "ui/shipments/<int:shipment_id>/labels/<int:carton_id>/",
        UiShipmentLabelDetailView.as_view(),
        name="ui-shipments-label-detail",
    ),
    path(
        "ui/templates/",
        UiPrintTemplatesView.as_view(),
        name="ui-print-templates",
    ),
    path(
        "ui/templates/<str:doc_type>/",
        UiPrintTemplateDetailView.as_view(),
        name="ui-print-template-detail",
    ),
    path(
        "ui/portal/dashboard/",
        UiPortalDashboardView.as_view(),
        name="ui-portal-dashboard",
    ),
    path(
        "ui/portal/orders/",
        UiPortalOrdersView.as_view(),
        name="ui-portal-orders",
    ),
    path(
        "ui/portal/orders/<int:order_id>/",
        UiPortalOrderDetailView.as_view(),
        name="ui-portal-order-detail",
    ),
    path(
        "ui/portal/recipients/",
        UiPortalRecipientsView.as_view(),
        name="ui-portal-recipients",
    ),
    path(
        "ui/portal/recipients/<int:recipient_id>/",
        UiPortalRecipientDetailView.as_view(),
        name="ui-portal-recipient-detail",
    ),
    path(
        "ui/portal/account/",
        UiPortalAccountView.as_view(),
        name="ui-portal-account",
    ),
]

urlpatterns += router.urls
