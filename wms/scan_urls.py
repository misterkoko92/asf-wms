from django.urls import path

from . import views

app_name = "scan"

urlpatterns = [
    path("", views.scan_stock, name="scan_root"),
    path("stock/", views.scan_stock, name="scan_stock"),
    path("cartons/", views.scan_cartons_ready, name="scan_cartons_ready"),
    path("shipments-ready/", views.scan_shipments_ready, name="scan_shipments_ready"),
    path("receive/", views.scan_receive, name="scan_receive"),
    path("receive-pallet/", views.scan_receive_pallet, name="scan_receive_pallet"),
    path("receive-association/", views.scan_receive_association, name="scan_receive_association"),
    path("stock-update/", views.scan_stock_update, name="scan_stock_update"),
    path("orders/", views.scan_order, name="scan_order"),
    path("pack/", views.scan_pack, name="scan_pack"),
    path("shipment/", views.scan_shipment_create, name="scan_shipment_create"),
    path(
        "shipment/<int:shipment_id>/edit/",
        views.scan_shipment_edit,
        name="scan_shipment_edit",
    ),
    path(
        "shipment/<int:shipment_id>/doc/<str:doc_type>/",
        views.scan_shipment_document,
        name="scan_shipment_document",
    ),
    path(
        "shipment/<int:shipment_id>/carton/<int:carton_id>/doc/",
        views.scan_shipment_carton_document,
        name="scan_shipment_carton_document",
    ),
    path(
        "shipment/<int:shipment_id>/documents/upload/",
        views.scan_shipment_document_upload,
        name="scan_shipment_document_upload",
    ),
    path(
        "shipment/<int:shipment_id>/documents/<int:document_id>/delete/",
        views.scan_shipment_document_delete,
        name="scan_shipment_document_delete",
    ),
    path("out/", views.scan_out, name="scan_out"),
    path("sync/", views.scan_sync, name="scan_sync"),
    path("service-worker.js", views.scan_service_worker, name="scan_service_worker"),
]
