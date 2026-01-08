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
]

urlpatterns += router.urls
