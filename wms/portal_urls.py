from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("login/", views.portal_login, name="portal_login"),
    path("logout/", views.portal_logout, name="portal_logout"),
    path("change-password/", views.portal_change_password, name="portal_change_password"),
    path(
        "set-password/<uidb64>/<token>/",
        views.portal_set_password,
        name="portal_set_password",
    ),
    path("request-account/", views.portal_account_request, name="portal_account_request"),
    path("", views.portal_dashboard, name="portal_dashboard"),
    path("orders/new/", views.portal_order_create, name="portal_order_create"),
    path("orders/<int:order_id>/", views.portal_order_detail, name="portal_order_detail"),
    path("recipients/", views.portal_recipients, name="portal_recipients"),
    path("account/", views.portal_account, name="portal_account"),
]
