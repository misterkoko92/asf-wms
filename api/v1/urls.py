from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, PackCartonView, ProductViewSet, ReceiveStockView

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("stock/receive/", ReceiveStockView.as_view(), name="stock-receive"),
    path("pack/", PackCartonView.as_view(), name="pack"),
]

urlpatterns += router.urls
