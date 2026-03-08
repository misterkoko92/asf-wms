from django.urls import path

from . import views

app_name = "volunteer"

urlpatterns = [
    path("request-account/", views.volunteer_account_request, name="request_account"),
    path(
        "request-account/done/",
        views.volunteer_account_request_done,
        name="request_account_done",
    ),
    path("login/", views.volunteer_login, name="login"),
    path("logout/", views.volunteer_logout, name="logout"),
    path(
        "set-password/<uidb64>/<token>/",
        views.volunteer_set_password,
        name="set_password",
    ),
    path("change-password/", views.volunteer_change_password, name="change_password"),
    path("profil/", views.volunteer_profile, name="profile"),
    path("contraintes/", views.volunteer_constraints, name="constraints"),
    path("disponibilites/", views.volunteer_availability_list, name="availability_list"),
    path(
        "disponibilites/nouveau/",
        views.volunteer_availability_create,
        name="availability_create",
    ),
    path(
        "disponibilites/recap/",
        views.volunteer_availability_recap,
        name="availability_recap",
    ),
    path(
        "disponibilites/<int:pk>/edit/",
        views.volunteer_availability_edit,
        name="availability_edit",
    ),
    path(
        "disponibilites/<int:pk>/delete/",
        views.volunteer_availability_delete,
        name="availability_delete",
    ),
    path("", views.volunteer_dashboard, name="dashboard"),
]
