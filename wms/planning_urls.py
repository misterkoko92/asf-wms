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
    path(
        "versions/<int:version_id>/clone/",
        views_planning.planning_version_clone,
        name="version_clone",
    ),
    path(
        "versions/<int:version_id>/publish/",
        views_planning.planning_version_publish,
        name="version_publish",
    ),
    path(
        "versions/<int:version_id>/diff/",
        views_planning.planning_version_diff,
        name="version_diff",
    ),
    path(
        "versions/<int:version_id>/communications/drafts/<int:draft_id>/action/",
        views_planning.planning_version_communication_draft_action,
        name="version_communication_draft_action",
    ),
    path(
        "versions/<int:version_id>/communications/families/<slug:family>/action/",
        views_planning.planning_version_communication_family_action,
        name="version_communication_family_action",
    ),
    path(
        "versions/<int:version_id>/communications/planning-workbook/",
        views_planning.planning_version_communication_workbook,
        name="version_communication_workbook",
    ),
    path(
        "versions/<int:version_id>/communications/shipments/<int:shipment_snapshot_id>/packing-list.pdf",
        views_planning.planning_version_communication_packing_list_pdf,
        name="version_communication_packing_list_pdf",
    ),
    path(
        "versions/<int:version_id>/communications/helper-installer/",
        views_planning.planning_version_communication_helper_installer,
        name="version_communication_helper_installer",
    ),
]
