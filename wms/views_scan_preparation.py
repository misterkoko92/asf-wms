from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms_preparation import (
    PreparationParameterSetForm,
    ScanPreparationRunForm,
    build_preparation_destination_rule_formset,
    build_preparation_shipper_rule_formset,
)
from .models import (
    Destination,
    PlanningParameterSet,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    ShipmentShipper,
)
from .planning.flight_providers import PlanningFlightProviderError
from .preparation.conversion import convert_preparation_run
from .preparation.generation import generate_preparation_run
from .preparation.review import (
    apply_preparation_review_action,
    carton_is_deleted,
    proposal_is_deleted,
)
from .view_permissions import scan_staff_required

TEMPLATE_PREPARATION_RUN_LIST = "scan/preparation_run_list.html"
TEMPLATE_PREPARATION_RUN_CREATE = "scan/preparation_run_create.html"
TEMPLATE_PREPARATION_RUN_DETAIL = "scan/preparation_run_detail.html"
TEMPLATE_PREPARATION_PARAMETER_SET_CONFIG = "scan/preparation_parameter_set_config.html"


def _current_planning_parameter_set():
    planning_parameter_set = (
        PlanningParameterSet.objects.filter(is_current=True).order_by("-updated_at", "-id").first()
    )
    if planning_parameter_set is not None:
        return planning_parameter_set
    return PlanningParameterSet.objects.order_by("-is_current", "name", "id").first()


def _planning_destination_defaults():
    planning_parameter_set = _current_planning_parameter_set()
    if planning_parameter_set is None:
        return {}

    defaults_by_destination = {}
    planning_rules = (
        planning_parameter_set.destination_rules.filter(
            is_active=True,
            destination__isnull=False,
        )
        .select_related("destination")
        .order_by("priority", "id")
    )
    for planning_rule in planning_rules:
        if planning_rule.destination_id in defaults_by_destination:
            continue
        weekly_frequency = planning_rule.weekly_frequency
        max_per_flight = planning_rule.max_cartons_per_flight
        defaults_by_destination[planning_rule.destination_id] = {
            "max_equivalent_units_per_flight": max_per_flight,
            "max_usable_flights_per_week": weekly_frequency,
            "max_equivalent_units_per_week": (
                max_per_flight * weekly_frequency
                if max_per_flight is not None and weekly_frequency is not None
                else None
            ),
            "max_shipments_per_week": weekly_frequency,
            "allowed_weekdays": list(planning_rule.allowed_weekdays or []),
        }
    return defaults_by_destination


def _backfill_destination_rule_from_planning_defaults(destination_rule, planning_defaults):
    defaults = planning_defaults.get(destination_rule.destination_id)
    if not defaults:
        return

    update_fields = []
    scalar_fields = (
        "max_equivalent_units_per_flight",
        "max_usable_flights_per_week",
        "max_equivalent_units_per_week",
        "max_shipments_per_week",
    )
    for field_name in scalar_fields:
        current_value = getattr(destination_rule, field_name)
        default_value = defaults.get(field_name)
        if current_value is None and default_value is not None:
            setattr(destination_rule, field_name, default_value)
            update_fields.append(field_name)

    if not destination_rule.allowed_weekdays and defaults.get("allowed_weekdays"):
        destination_rule.allowed_weekdays = defaults["allowed_weekdays"]
        update_fields.append("allowed_weekdays")

    if update_fields:
        destination_rule.save(update_fields=update_fields)


def _default_parameter_set_for_config(*, user):
    parameter_set = PreparationParameterSet.objects.order_by(
        "-is_current", "-updated_at", "-id"
    ).first()
    if parameter_set is not None:
        return parameter_set
    return PreparationParameterSet.objects.create(
        name="Jeu de paramètres magasin",
        notes="Créé automatiquement pour initialiser la configuration du run magasin.",
        is_current=True,
        created_by=user,
    )


def _resolve_parameter_set_for_config(request):
    raw_parameter_set_id = (
        request.POST.get("parameter_set_id")
        or request.GET.get("parameter_set")
        or request.GET.get("parameter_set_id")
    )
    if raw_parameter_set_id:
        return get_object_or_404(PreparationParameterSet, pk=raw_parameter_set_id)
    return _default_parameter_set_for_config(user=request.user)


def _ensure_parameter_set_scope_rules(parameter_set):
    planning_defaults = _planning_destination_defaults()
    for destination in Destination.objects.filter(is_active=True).order_by(
        "city", "iata_code", "id"
    ):
        destination_rule, created = PreparationDestinationRule.objects.get_or_create(
            parameter_set=parameter_set,
            destination=destination,
            defaults=planning_defaults.get(destination.id, {}),
        )
        if not created:
            _backfill_destination_rule_from_planning_defaults(destination_rule, planning_defaults)
    for shipper in (
        ShipmentShipper.objects.filter(is_active=True, organization__is_active=True)
        .select_related("organization")
        .order_by("organization__name", "id")
    ):
        PreparationShipperRule.objects.get_or_create(
            parameter_set=parameter_set,
            shipper=shipper,
            defaults={"mode": PreparationShipperMode.DEPOSIT_ONLY},
        )


def _build_preparation_proposal_rows(run):
    proposals = (
        run.shipment_proposals.select_related(
            "shipper__organization",
            "recipient_organization__organization",
            "destination",
        )
        .prefetch_related("carton_proposals")
        .order_by(
            "shipper__organization__name",
            "recipient_organization__organization__name",
            "sequence",
            "id",
        )
    )
    rows = []
    for proposal in proposals:
        if proposal_is_deleted(proposal):
            continue
        rationale = proposal.rationale or {}
        carton_rows = []
        for carton in proposal.carton_proposals.order_by("id"):
            if carton_is_deleted(carton):
                continue
            carton_rows.append(
                {
                    "id": carton.id,
                    "product_label": getattr(carton.product, "name", "Colis déposé"),
                    "quantity": carton.quantity,
                    "source": carton.source,
                    "status": carton.status,
                    "reservation_count": carton.reservations.count(),
                }
            )
        rows.append(
            {
                "id": proposal.id,
                "shipper_name": proposal.shipper.organization.name,
                "recipient_name": proposal.recipient_organization.organization.name,
                "destination_label": f"{proposal.destination.city} ({proposal.destination.iata_code})",
                "sequence": proposal.sequence,
                "equivalent_units_total": proposal.equivalent_units_total,
                "status": proposal.status,
                "needs_recalc": proposal.status == PreparationShipmentProposalStatus.NEEDS_RECALC,
                "score_reasons": rationale.get("reasons") or [],
                "carton_count": len(carton_rows),
                "carton_rows": carton_rows,
            }
        )
    return rows


@scan_staff_required
@require_http_methods(["GET"])
def scan_preparation_run_list(request):
    runs = PreparationRun.objects.select_related("parameter_set", "created_by").order_by(
        "-created_at", "-id"
    )
    return render(
        request,
        TEMPLATE_PREPARATION_RUN_LIST,
        {
            "active": "preparation_runs",
            "runs": runs,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparation_run_create(request):
    form = ScanPreparationRunForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        cleaned = form.cleaned_data
        run = PreparationRun.objects.create(
            parameter_set=cleaned["parameter_set"],
            created_by=request.user,
            target_equivalent_units=cleaned["target_equivalent_units"],
            target_shipment_count=cleaned["target_shipment_count"],
            target_shipment_size_units=cleaned["target_shipment_size_units"],
            min_shipment_size_units=cleaned["min_shipment_size_units"],
            max_shipment_size_units=cleaned["max_shipment_size_units"],
            flight_window_start=cleaned["flight_window_start"],
            flight_window_end=cleaned["flight_window_end"],
        )
        try:
            generate_preparation_run(
                run=run,
                shippers=list(cleaned["shippers"]),
                destinations=list(cleaned["destinations"]),
            )
        except PlanningFlightProviderError as exc:
            run.delete()
            form.add_error(
                None,
                f"Impossible de charger les vols pour ce run magasin: {exc}",
            )
        else:
            return redirect("scan:scan_preparation_run_detail", run_id=run.id)

    return render(
        request,
        TEMPLATE_PREPARATION_RUN_CREATE,
        {
            "active": "preparation_runs",
            "form": form,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparation_parameter_set_config(request):
    parameter_set = _resolve_parameter_set_for_config(request)
    _ensure_parameter_set_scope_rules(parameter_set)

    if request.method == "POST":
        parameter_form = PreparationParameterSetForm(
            request.POST,
            instance=parameter_set,
            prefix="parameter",
        )
        destination_formset = build_preparation_destination_rule_formset(
            parameter_set,
            data=request.POST,
        )
        shipper_formset = build_preparation_shipper_rule_formset(
            parameter_set,
            data=request.POST,
        )
        if (
            parameter_form.is_valid()
            and destination_formset.is_valid()
            and shipper_formset.is_valid()
        ):
            with transaction.atomic():
                saved_parameter_set = parameter_form.save(commit=False)
                if saved_parameter_set.is_current:
                    PreparationParameterSet.objects.exclude(pk=saved_parameter_set.pk).filter(
                        is_current=True
                    ).update(is_current=False)
                saved_parameter_set.save()
                destination_formset.save()
                shipper_formset.save()
            messages.success(request, "Jeu de paramètres enregistré.")
            return redirect(f"{request.path}?parameter_set={saved_parameter_set.id}")
    else:
        parameter_form = PreparationParameterSetForm(
            instance=parameter_set,
            prefix="parameter",
        )
        destination_formset = build_preparation_destination_rule_formset(parameter_set)
        shipper_formset = build_preparation_shipper_rule_formset(parameter_set)

    return render(
        request,
        TEMPLATE_PREPARATION_PARAMETER_SET_CONFIG,
        {
            "active": "preparation_runs",
            "parameter_set": parameter_set,
            "parameter_set_choices": PreparationParameterSet.objects.order_by(
                "-is_current",
                "name",
                "id",
            ),
            "parameter_form": parameter_form,
            "destination_formset": destination_formset,
            "shipper_formset": shipper_formset,
        },
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparation_run_detail(request, run_id):
    run = get_object_or_404(
        PreparationRun.objects.select_related("parameter_set", "created_by"),
        pk=run_id,
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action:
            if action == "convert_accepted":
                created_shipments = convert_preparation_run(run=run, created_by=request.user)
                if created_shipments:
                    messages.success(
                        request,
                        f"{len(created_shipments)} expédition(s) créée(s) en préparation.",
                    )
                else:
                    messages.warning(request, "Aucune proposition validée à convertir.")
            else:
                processed = apply_preparation_review_action(
                    run=run,
                    action=action,
                    selected_shipment_ids=request.POST.getlist("selected_shipment_ids"),
                    selected_carton_ids=request.POST.getlist("selected_carton_ids"),
                    created_by=request.user,
                )
                if processed:
                    messages.success(request, f"{processed} proposition(s) mise(s) à jour.")
                else:
                    messages.warning(request, "Aucune proposition sélectionnée.")
        return redirect("scan:scan_preparation_run_detail", run_id=run.id)
    flight_source = (run.parameter_snapshot or {}).get("flight_source") or {}
    fallback_warning = None
    if flight_source.get("used_fallback"):
        fallback_warning = {
            "reason": flight_source.get("fallback_reason") or "fallback enabled",
            "freshness_days": flight_source.get("freshness_days"),
        }
    return render(
        request,
        TEMPLATE_PREPARATION_RUN_DETAIL,
        {
            "active": "preparation_runs",
            "run": run,
            "proposal_rows": _build_preparation_proposal_rows(run),
            "fallback_warning": fallback_warning,
        },
    )
