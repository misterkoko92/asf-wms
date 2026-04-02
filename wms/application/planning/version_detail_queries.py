from wms.models import PlanningVersionStatus
from wms.planning.operator_options import (
    build_assignment_editor_options,
    build_operator_option_context,
    build_unassigned_editor_options,
)
from wms.planning.version_dashboard import build_version_dashboard


def _attach_assignment_forms(dashboard, assignment_formset):
    if assignment_formset is None:
        return
    forms_by_id = {form.instance.pk: form for form in assignment_formset}
    for group in dashboard["flight_groups"]:
        for assignment in group["assignments"]:
            assignment["form"] = forms_by_id.get(assignment["assignment_id"])


def _attach_operator_options(version, dashboard):
    if version.status != PlanningVersionStatus.DRAFT:
        return
    context = build_operator_option_context(version)
    assignments_by_id = {
        assignment.pk: assignment
        for assignment in version.assignments.select_related(
            "shipment_snapshot",
            "volunteer_snapshot",
            "flight_snapshot",
        )
    }
    for row in dashboard["planning_rows"]:
        assignment = assignments_by_id.get(row["assignment_id"])
        if assignment is None:
            continue
        row["editor_options"] = build_assignment_editor_options(
            version,
            assignment=assignment,
            context=context,
        )
    for group in dashboard["flight_groups"]:
        for assignment_row in group["assignments"]:
            assignment = assignments_by_id.get(assignment_row["assignment_id"])
            if assignment is None:
                continue
            assignment_row["editor_options"] = build_assignment_editor_options(
                version,
                assignment=assignment,
                context=context,
            )

    shipments_by_id = {snapshot.pk: snapshot for snapshot in version.run.shipment_snapshots.all()}
    for row in dashboard["unassigned_shipments"]:
        shipment_snapshot = shipments_by_id.get(row["shipment_snapshot_id"])
        if shipment_snapshot is None:
            continue
        row["editor_options"] = build_unassigned_editor_options(
            version,
            shipment_snapshot=shipment_snapshot,
            context=context,
        )


def _attach_draft_forms(dashboard, draft_formset):
    if draft_formset is None:
        return
    forms_by_id = {form.instance.pk: form for form in draft_formset}
    for group in dashboard["communications"]["groups"]:
        for draft in group["drafts"]:
            draft["form"] = forms_by_id.get(draft["draft_id"])


def _build_version_priority_cards(version, dashboard):
    unassigned_count = dashboard["stats"]["unassigned_count"]
    draft_count = dashboard["communications"]["draft_count"]
    manual_adjustment_count = dashboard["stats"]["manual_adjustment_count"]
    artifact_count = dashboard["exports"]["artifact_count"]
    return [
        {
            "label": "Non affectes",
            "value": unassigned_count,
            "help": "Expeditions encore hors planning pour cette version.",
            "cta_label": "Traiter",
            "url": "#planning-version-non-affectes",
            "tone": "warning" if unassigned_count else "neutral",
        },
        {
            "label": "Communications",
            "value": draft_count,
            "help": "Brouillons a verifier ou a generer.",
            "cta_label": "Ouvrir",
            "url": "#planning-version-communications",
            "tone": "primary" if draft_count else "neutral",
        },
        {
            "label": "Ajustements manuels",
            "value": manual_adjustment_count,
            "help": "Affectations corrigees hors solveur.",
            "cta_label": "Revoir",
            "url": "#planning-version-planning",
            "tone": "warning" if manual_adjustment_count else "neutral",
        },
        {
            "label": "Exports",
            "value": artifact_count,
            "help": "Artefacts disponibles pour cette version.",
            "cta_label": "Exporter",
            "url": "#planning-version-exports",
            "tone": "neutral",
        },
    ]


def build_planning_version_detail_payload(
    *,
    version,
    assignment_formset=None,
    draft_formset=None,
):
    dashboard = build_version_dashboard(version)
    _attach_assignment_forms(
        dashboard,
        assignment_formset if version.status == PlanningVersionStatus.DRAFT else None,
    )
    _attach_operator_options(version, dashboard)
    _attach_draft_forms(dashboard, draft_formset)
    return {
        "dashboard": dashboard,
        "priority_cards": _build_version_priority_cards(version, dashboard),
    }
