from pathlib import Path

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms_planning import (
    PlanningRunForm,
    PlanningVersionCloneForm,
    build_assignment_formset,
    build_communication_draft_formset,
)
from .models import (
    CommunicationDraftStatus,
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from .planning.communication_actions import (
    PACKING_LIST_ATTACHMENT,
    PLANNING_WORKBOOK_ATTACHMENT,
    build_draft_helper_action_payload,
    build_family_helper_action_payload,
)
from .planning.communications import generate_version_drafts
from .planning.exports import export_version_workbook
from .planning.operator_mutations import (
    assign_unassigned_shipment,
    delete_assignment,
    update_assignment,
)
from .planning.operator_options import (
    build_assignment_editor_options,
    build_operator_option_context,
    build_unassigned_editor_options,
)
from .planning.shipment_updates import apply_version_updates
from .planning.snapshots import prepare_run_inputs
from .planning.solver import solve_run
from .planning.version_dashboard import build_version_dashboard
from .planning.versioning import clone_version, diff_versions, publish_version
from .print_pack_engine import PrintPackEngineError, generate_pack
from .print_pack_graph import GraphPdfConversionError
from .print_pack_routing import resolve_pack_request
from .view_permissions import scan_staff_required

TEMPLATE_RUN_LIST = "planning/run_list.html"
TEMPLATE_RUN_CREATE = "planning/run_create.html"
TEMPLATE_RUN_DETAIL = "planning/run_detail.html"
TEMPLATE_VERSION_DETAIL = "planning/version_detail.html"
TEMPLATE_VERSION_DIFF = "planning/version_diff.html"
ACTIVE_PLANNING_RUNS = "planning_runs"


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
    forms_by_id = {form.instance.pk: form for form in draft_formset}
    for group in dashboard["communications"]["groups"]:
        for draft in group["drafts"]:
            draft["form"] = forms_by_id.get(draft["draft_id"])


def _validation_error_message(exc: ValidationError) -> str:
    if getattr(exc, "messages", None):
        return "; ".join(exc.messages)
    return str(exc)


def _communication_attachment_download_url(version, attachment):
    attachment_type = attachment.get("attachment_type")
    if attachment_type == PLANNING_WORKBOOK_ATTACHMENT:
        return reverse("planning:version_communication_workbook", args=[version.pk])
    if attachment_type == PACKING_LIST_ATTACHMENT:
        return reverse(
            "planning:version_communication_packing_list_pdf",
            args=[version.pk, attachment.get("shipment_snapshot_id")],
        )
    return ""


def _decorate_helper_payload(version, payload):
    decorated = dict(payload)
    if "attachments" in payload:
        decorated["attachments"] = []
        for attachment in payload.get("attachments", []):
            attachment_payload = dict(attachment)
            attachment_payload["download_url"] = _communication_attachment_download_url(
                version,
                attachment_payload,
            )
            decorated["attachments"].append(attachment_payload)
    if "drafts" in payload:
        decorated["drafts"] = [
            _decorate_helper_payload(version, draft_payload)
            for draft_payload in payload.get("drafts", [])
        ]
    return decorated


def _build_workbook_file_response(version):
    artifact = export_version_workbook(version)
    filename = Path(artifact.file_path).name or f"planning-v{version.number}.xlsx"
    response = FileResponse(
        open(artifact.file_path, "rb"),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_strict_packing_list_pdf_response(request, shipment_snapshot):
    if shipment_snapshot.shipment_id is None:
        raise ValidationError("Aucune expédition source n'est liée à ce snapshot.")

    pack_route = resolve_pack_request("packing_list_shipment")
    if pack_route is None:
        raise ValidationError("Route packing list indisponible.")

    try:
        artifact = generate_pack(
            pack_code=pack_route.pack_code,
            shipment=shipment_snapshot.shipment,
            user=getattr(request, "user", None),
            variant=pack_route.variant,
        )
    except (GraphPdfConversionError, PrintPackEngineError) as exc:
        raise ValidationError("PDF packing list indisponible.") from exc

    filename = (artifact.pdf_file.name or "").split("/")[-1]
    if not filename:
        filename = f"packing-list-{shipment_snapshot.shipment_reference}.pdf"
    response = FileResponse(
        artifact.pdf_file.open("rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@scan_staff_required
@require_http_methods(["GET"])
def planning_run_list(request):
    runs = PlanningRun.objects.select_related(
        "parameter_set", "flight_batch", "created_by"
    ).prefetch_related(
        "issues",
        "versions",
    )
    return render(
        request,
        TEMPLATE_RUN_LIST,
        {
            "active": ACTIVE_PLANNING_RUNS,
            "runs": runs,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def planning_run_create(request):
    if request.method == "POST":
        form = PlanningRunForm(request.POST)
        if form.is_valid():
            run = form.save(commit=False)
            run.created_by = request.user
            run.save()
            messages.success(request, "Run de planning cree.")
            return redirect("planning:run_detail", run.pk)
    else:
        form = PlanningRunForm()
    return render(
        request,
        TEMPLATE_RUN_CREATE,
        {
            "active": ACTIVE_PLANNING_RUNS,
            "form": form,
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def planning_run_detail(request, run_id):
    run = get_object_or_404(
        PlanningRun.objects.select_related(
            "parameter_set", "flight_batch", "created_by"
        ).prefetch_related(
            "issues",
            "versions",
        ),
        pk=run_id,
    )
    return render(
        request,
        TEMPLATE_RUN_DETAIL,
        {
            "active": ACTIVE_PLANNING_RUNS,
            "run": run,
            "issues": run.issues.all(),
            "versions": run.versions.all(),
            "solve_url": None if run.status != "ready" else request.build_absolute_uri(),
        },
    )


@scan_staff_required
@require_http_methods(["POST"])
def planning_run_solve(request, run_id):
    run = get_object_or_404(PlanningRun, pk=run_id)
    if run.status in {PlanningRunStatus.VALIDATING, PlanningRunStatus.SOLVING}:
        messages.error(request, "Le run est deja en cours de traitement.")
        return redirect("planning:run_detail", run.pk)

    if run.status != PlanningRunStatus.READY:
        prepare_run_inputs(run)
        run.refresh_from_db()
    if run.status != PlanningRunStatus.READY:
        messages.error(
            request,
            "La validation du run a echoue. Corrigez les issues puis relancez.",
        )
        return redirect("planning:run_detail", run.pk)

    version = solve_run(run)
    messages.success(request, "Planning genere et version brouillon creee.")
    return redirect("planning:version_detail", version.pk)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def planning_version_detail(request, version_id):
    version = get_object_or_404(
        PlanningVersion.objects.select_related("run", "based_on", "created_by").prefetch_related(
            "assignments__shipment_snapshot",
            "assignments__volunteer_snapshot",
            "assignments__flight_snapshot",
            "communication_drafts__template",
            "artifacts",
        ),
        pk=version_id,
    )
    assignment_formset = build_assignment_formset(version)
    draft_formset = build_communication_draft_formset(version)

    if request.method == "POST":
        if request.POST.get("assignment_action") == "delete":
            try:
                delete_assignment(
                    version=version,
                    assignment=get_object_or_404(
                        PlanningAssignment.objects.select_related("version"),
                        pk=request.POST.get("assignment_id"),
                    ),
                )
            except ValidationError as exc:
                messages.error(request, _validation_error_message(exc))
            else:
                messages.success(request, "Expedition retiree du planning.")
            return redirect("planning:version_detail", version.pk)
        elif request.POST.get("assignment_action") == "update":
            assignment = get_object_or_404(
                PlanningAssignment.objects.select_related("shipment_snapshot", "version"),
                pk=request.POST.get("assignment_id"),
            )
            volunteer_snapshot = get_object_or_404(
                PlanningVolunteerSnapshot,
                pk=request.POST.get("volunteer_snapshot"),
                run=version.run,
            )
            flight_snapshot = get_object_or_404(
                PlanningFlightSnapshot,
                pk=request.POST.get("flight_snapshot"),
                run=version.run,
            )
            try:
                update_assignment(
                    version=version,
                    assignment=assignment,
                    volunteer_snapshot=volunteer_snapshot,
                    flight_snapshot=flight_snapshot,
                )
            except ValidationError as exc:
                messages.error(request, _validation_error_message(exc))
            else:
                messages.success(request, "Affectation mise a jour.")
            return redirect("planning:version_detail", version.pk)
        elif request.POST.get("assignment_action") == "save":
            if version.status != PlanningVersionStatus.DRAFT:
                messages.error(request, "Seules les versions brouillon sont modifiables.")
                return redirect("planning:version_detail", version.pk)

            assignment_formset = build_assignment_formset(version, data=request.POST)
            if assignment_formset.is_valid():
                updated_assignments = assignment_formset.save(commit=False)
                for assignment in updated_assignments:
                    assignment.source = PlanningAssignmentSource.MANUAL
                    assignment.save()
                messages.success(request, "Affectations mises a jour.")
                return redirect("planning:version_detail", version.pk)
        elif request.POST.get("draft_action") == "generate":
            if version.status != PlanningVersionStatus.PUBLISHED:
                messages.error(
                    request,
                    "Seules les versions publiees peuvent generer des brouillons.",
                )
                return redirect("planning:version_detail", version.pk)
            generate_version_drafts(version)
            messages.success(request, "Brouillons de communication regeneres.")
            return redirect("planning:version_detail", version.pk)
        elif request.POST.get("draft_action") == "save":
            draft_formset = build_communication_draft_formset(version, data=request.POST)
            if draft_formset.is_valid():
                updated_drafts = draft_formset.save(commit=False)
                for draft in updated_drafts:
                    draft.status = CommunicationDraftStatus.EDITED
                    draft.edited_by = request.user
                    draft.edited_at = timezone.now()
                    draft.save()
                messages.success(request, "Brouillons mis a jour.")
                return redirect("planning:version_detail", version.pk)
        elif request.POST.get("artifact_action") == "export":
            export_version_workbook(version)
            messages.success(request, "Export Planning.xlsx regenere.")
            return redirect("planning:version_detail", version.pk)
        elif request.POST.get("shipment_action") == "apply_updates":
            summary = apply_version_updates(
                version,
                actor_name=request.user.get_username() or "planner",
                user=request.user,
            )
            messages.success(
                request,
                "Mises a jour expedition appliquees: {updated} mise(s) a jour, "
                "{locked} ignoree(s), {events} evenement(s) tracking cree(s).".format(
                    updated=summary["updated"],
                    locked=summary["skipped_locked"],
                    events=summary["tracking_events_created"],
                ),
            )
            return redirect("planning:version_detail", version.pk)
        elif request.POST.get("shipment_action") == "assign":
            shipment_snapshot = get_object_or_404(
                PlanningShipmentSnapshot,
                pk=request.POST.get("shipment_snapshot_id"),
                run=version.run,
            )
            volunteer_snapshot = get_object_or_404(
                PlanningVolunteerSnapshot,
                pk=request.POST.get("volunteer_snapshot"),
                run=version.run,
            )
            flight_snapshot = get_object_or_404(
                PlanningFlightSnapshot,
                pk=request.POST.get("flight_snapshot"),
                run=version.run,
            )
            try:
                assign_unassigned_shipment(
                    version=version,
                    shipment_snapshot=shipment_snapshot,
                    volunteer_snapshot=volunteer_snapshot,
                    flight_snapshot=flight_snapshot,
                )
            except ValidationError as exc:
                messages.error(request, _validation_error_message(exc))
            else:
                messages.success(request, "Expedition ajoutee au planning.")
            return redirect("planning:version_detail", version.pk)

    dashboard = build_version_dashboard(version)
    _attach_assignment_forms(
        dashboard,
        assignment_formset if version.status == PlanningVersionStatus.DRAFT else None,
    )
    _attach_operator_options(version, dashboard)
    _attach_draft_forms(dashboard, draft_formset)

    return render(
        request,
        TEMPLATE_VERSION_DETAIL,
        {
            "active": ACTIVE_PLANNING_RUNS,
            "version": version,
            "assignments": version.assignments.all(),
            "assignment_formset": assignment_formset
            if version.status == PlanningVersionStatus.DRAFT
            else None,
            "draft_formset": draft_formset,
            "artifacts": version.artifacts.all(),
            "dashboard": dashboard,
            "clone_form": PlanningVersionCloneForm(),
        },
    )


@scan_staff_required
@require_http_methods(["GET"])
def planning_version_communication_draft_action(request, version_id, draft_id):
    version = get_object_or_404(PlanningVersion, pk=version_id)
    draft = get_object_or_404(version.communication_drafts.all(), pk=draft_id)
    try:
        payload = build_draft_helper_action_payload(draft)
    except ValidationError as exc:
        return JsonResponse({"error": _validation_error_message(exc)}, status=409)
    return JsonResponse(_decorate_helper_payload(version, payload))


@scan_staff_required
@require_http_methods(["GET"])
def planning_version_communication_family_action(request, version_id, family):
    version = get_object_or_404(PlanningVersion, pk=version_id)
    try:
        payload = build_family_helper_action_payload(version=version, family=family)
    except ValidationError as exc:
        return JsonResponse({"error": _validation_error_message(exc)}, status=409)
    return JsonResponse(_decorate_helper_payload(version, payload))


@scan_staff_required
@require_http_methods(["GET"])
def planning_version_communication_workbook(request, version_id):
    version = get_object_or_404(PlanningVersion, pk=version_id)
    return _build_workbook_file_response(version)


@scan_staff_required
@require_http_methods(["GET"])
def planning_version_communication_packing_list_pdf(request, version_id, shipment_snapshot_id):
    version = get_object_or_404(PlanningVersion.objects.select_related("run"), pk=version_id)
    shipment_snapshot = get_object_or_404(
        PlanningShipmentSnapshot.objects.select_related("shipment"),
        pk=shipment_snapshot_id,
        run=version.run,
    )
    try:
        return _build_strict_packing_list_pdf_response(request, shipment_snapshot)
    except ValidationError as exc:
        return JsonResponse({"error": _validation_error_message(exc)}, status=409)


@scan_staff_required
@require_http_methods(["POST"])
def planning_version_clone(request, version_id):
    version = get_object_or_404(PlanningVersion, pk=version_id)
    form = PlanningVersionCloneForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Le motif de changement est invalide.")
        return redirect("planning:version_detail", version.pk)

    cloned_version = clone_version(
        version,
        created_by=request.user,
        change_reason=form.cleaned_data["change_reason"],
    )
    messages.success(request, "Nouvelle version brouillon creee.")
    return redirect("planning:version_detail", cloned_version.pk)


@scan_staff_required
@require_http_methods(["POST"])
def planning_version_publish(request, version_id):
    version = get_object_or_404(PlanningVersion, pk=version_id)
    publish_version(version)
    messages.success(request, "Version publiee.")
    return redirect("planning:version_detail", version.pk)


@scan_staff_required
@require_http_methods(["GET"])
def planning_version_diff(request, version_id):
    version = get_object_or_404(
        PlanningVersion.objects.select_related("run", "based_on"),
        pk=version_id,
    )
    if version.based_on_id is None:
        raise Http404("This version has no parent to compare against.")
    comparison = diff_versions(version.based_on, version)
    return render(
        request,
        TEMPLATE_VERSION_DIFF,
        {
            "active": ACTIVE_PLANNING_RUNS,
            "version": version,
            "previous_version": version.based_on,
            "comparison": comparison,
        },
    )
