from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
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
    PlanningAssignmentSource,
    PlanningRun,
    PlanningVersion,
    PlanningVersionStatus,
)
from .planning.communications import generate_version_drafts
from .planning.exports import export_version_workbook
from .planning.solver import solve_run
from .planning.stats import build_version_stats
from .planning.versioning import clone_version, diff_versions, publish_version
from .view_permissions import scan_staff_required

TEMPLATE_RUN_LIST = "planning/run_list.html"
TEMPLATE_RUN_CREATE = "planning/run_create.html"
TEMPLATE_RUN_DETAIL = "planning/run_detail.html"
TEMPLATE_VERSION_DETAIL = "planning/version_detail.html"
TEMPLATE_VERSION_DIFF = "planning/version_diff.html"
ACTIVE_PLANNING_RUNS = "planning_runs"


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
    version = solve_run(run)
    messages.success(request, "Solveur lance et version brouillon creee.")
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
        if request.POST.get("assignment_action") == "save":
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
            "version_stats": build_version_stats(version),
            "clone_form": PlanningVersionCloneForm(),
        },
    )


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
