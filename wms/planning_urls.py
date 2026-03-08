from django.urls import path

from . import views_planning

app_name = "planning"

urlpatterns = [
    path("", views_planning.planning_run_list, name="run_list"),
    path("runs/new/", views_planning.planning_run_create, name="run_create"),
    path("runs/<int:run_id>/", views_planning.planning_run_detail, name="run_detail"),
    path("runs/<int:run_id>/solve/", views_planning.planning_run_solve, name="run_solve"),
    path(
        "versions/<int:version_id>/",
        views_planning.planning_version_detail,
        name="version_detail",
    ),
]
