from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .billing_document_handlers import (
    build_editor_candidates,
    create_billing_draft,
    issue_billing_document,
)
from .billing_exchange_rates import resolve_exchange_rate
from .billing_permissions import require_billing_staff_or_superuser
from .forms_billing import (
    BillingAssociationPriceOverrideForm,
    BillingComputationProfileForm,
    BillingDocumentDraftOptionsForm,
    BillingServiceCatalogItemForm,
    ShipmentUnitEquivalenceRuleForm,
)
from .models import (
    AssociationProfile,
    BillingAssociationPriceOverride,
    BillingComputationProfile,
    BillingDocument,
    BillingDocumentKind,
    BillingServiceCatalogItem,
    ShipmentUnitEquivalenceRule,
)
from .view_permissions import require_superuser as _require_superuser
from .view_permissions import scan_staff_required

TEMPLATE_SCAN_BILLING_SETTINGS = "scan/billing_settings.html"
TEMPLATE_SCAN_BILLING_EQUIVALENCE = "scan/billing_equivalence.html"
TEMPLATE_SCAN_BILLING_EDITOR = "scan/billing_editor.html"
ACTION_SAVE_PROFILE = "save_profile"
ACTION_SAVE_SERVICE = "save_service"
ACTION_SAVE_OVERRIDE = "save_override"
ACTION_SAVE_EQUIVALENCE_RULE = "save_equivalence_rule"
ACTION_BUILD_DRAFT = "build_draft"
ACTION_ISSUE_DOCUMENT = "issue_document"


def _selected_instance_from_query(request, *, query_key, model):
    object_id = (request.GET.get(query_key) or "").strip()
    if not object_id:
        return None
    return get_object_or_404(model, pk=object_id)


def _build_billing_settings_context(
    *,
    active,
    profile_form,
    service_form,
    override_form,
):
    return {
        "active": active,
        "profile_form": profile_form,
        "service_form": service_form,
        "override_form": override_form,
        "computation_profiles": BillingComputationProfile.objects.order_by("label", "code"),
        "service_catalog_items": BillingServiceCatalogItem.objects.order_by(
            "display_order", "label"
        ),
        "association_price_overrides": BillingAssociationPriceOverride.objects.select_related(
            "association_billing_profile__association_profile__contact",
            "service_catalog_item",
            "computation_profile",
        ).order_by(
            "association_billing_profile__association_profile__contact__name",
            "id",
        ),
    }


def _category_depth(category):
    depth = 0
    current = category
    while current is not None:
        depth += 1
        current = current.parent
    return depth


def _equivalence_rule_sort_key(rule):
    return (
        0 if rule.is_active else 1,
        -1 if rule.applies_to_hors_format else 0,
        -_category_depth(rule.category),
        rule.priority,
        rule.label.lower(),
    )


def _build_billing_equivalence_context(*, active, rule_form):
    equivalence_rules = list(
        ShipmentUnitEquivalenceRule.objects.select_related("category", "category__parent")
    )
    equivalence_rules.sort(key=_equivalence_rule_sort_key)
    for rule in equivalence_rules:
        rule.category_depth = _category_depth(rule.category)
    return {
        "active": active,
        "rule_form": rule_form,
        "equivalence_rules": equivalence_rules,
    }


def _selected_association_profile(raw_value):
    association_profile_id = (raw_value or "").strip()
    if not association_profile_id:
        return None
    return (
        AssociationProfile.objects.select_related("contact", "billing_profile")
        .filter(pk=association_profile_id)
        .first()
    )


def _resolved_period(request):
    period_start = parse_date(
        (request.POST.get("period_start") or request.GET.get("period_start") or "").strip()
    )
    period_end = parse_date(
        (request.POST.get("period_end") or request.GET.get("period_end") or "").strip()
    )
    if period_start or period_end:
        return (period_start, period_end)
    return None


def _build_billing_editor_context(
    *,
    active,
    association_profile,
    kind,
    period,
    candidate_rows,
    draft_document,
    draft_options_form,
    exchange_rate_resolution,
):
    return {
        "active": active,
        "association_profiles": AssociationProfile.objects.select_related("contact").order_by(
            "contact__name",
            "id",
        ),
        "selected_association_profile": association_profile,
        "selected_kind": kind,
        "selected_period_start": period[0] if period else None,
        "selected_period_end": period[1] if period else None,
        "candidate_rows": candidate_rows,
        "draft_document": draft_document,
        "draft_options_form": draft_options_form,
        "billing_document_kind_choices": BillingDocumentKind.choices,
        "exchange_rate_resolution": exchange_rate_resolution,
    }


def _selected_document_currency(request, association_profile):
    raw_currency = (
        request.POST.get("currency") if request.method == "POST" else request.GET.get("currency")
    )
    normalized_currency = (raw_currency or "").strip().upper()
    if normalized_currency:
        return normalized_currency
    if association_profile is not None:
        default_currency = (association_profile.billing_profile.default_currency or "").strip()
        if default_currency:
            return default_currency.upper()
    return "EUR"


def _initial_exchange_rate_value(request, exchange_rate_resolution):
    raw_exchange_rate = (
        request.POST.get("exchange_rate")
        if request.method == "POST"
        else request.GET.get("exchange_rate")
    )
    normalized_exchange_rate = (raw_exchange_rate or "").strip()
    if normalized_exchange_rate:
        return normalized_exchange_rate
    if exchange_rate_resolution.rate is not None:
        return format(exchange_rate_resolution.rate, "f")
    return ""


def _build_draft_options_form(*, request, action, selected_currency, exchange_rate_resolution):
    initial_values = {
        "currency": selected_currency,
        "exchange_rate": _initial_exchange_rate_value(request, exchange_rate_resolution),
    }
    if request.method == "POST" and action == ACTION_BUILD_DRAFT:
        form_data = request.POST.copy()
        if not (form_data.get("currency") or "").strip():
            form_data["currency"] = initial_values["currency"]
        if not (form_data.get("exchange_rate") or "").strip() and initial_values["exchange_rate"]:
            form_data["exchange_rate"] = initial_values["exchange_rate"]
        return BillingDocumentDraftOptionsForm(form_data, initial=initial_values)
    return BillingDocumentDraftOptionsForm(initial=initial_values)


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_billing_settings(request):
    _require_superuser(request)
    profile_instance = _selected_instance_from_query(
        request,
        query_key="edit_profile",
        model=BillingComputationProfile,
    )
    service_instance = _selected_instance_from_query(
        request,
        query_key="edit_service",
        model=BillingServiceCatalogItem,
    )
    override_instance = _selected_instance_from_query(
        request,
        query_key="edit_override",
        model=BillingAssociationPriceOverride,
    )

    profile_form = BillingComputationProfileForm(instance=profile_instance)
    service_form = BillingServiceCatalogItemForm(instance=service_instance)
    override_form = BillingAssociationPriceOverrideForm(instance=override_instance)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == ACTION_SAVE_PROFILE:
            profile_id = (request.POST.get("profile_id") or "").strip()
            profile_instance = (
                get_object_or_404(BillingComputationProfile, pk=profile_id) if profile_id else None
            )
            profile_form = BillingComputationProfileForm(request.POST, instance=profile_instance)
            if profile_form.is_valid():
                saved_profile = profile_form.save()
                messages.success(request, f'Profil de calcul "{saved_profile.label}" enregistre.')
                return redirect("scan:scan_billing_settings")
        elif action == ACTION_SAVE_SERVICE:
            service_id = (request.POST.get("service_id") or "").strip()
            service_instance = (
                get_object_or_404(BillingServiceCatalogItem, pk=service_id) if service_id else None
            )
            service_form = BillingServiceCatalogItemForm(request.POST, instance=service_instance)
            if service_form.is_valid():
                saved_service = service_form.save()
                messages.success(request, f'Service "{saved_service.label}" enregistre.')
                return redirect("scan:scan_billing_settings")
        elif action == ACTION_SAVE_OVERRIDE:
            override_id = (request.POST.get("override_id") or "").strip()
            override_instance = (
                get_object_or_404(BillingAssociationPriceOverride, pk=override_id)
                if override_id
                else None
            )
            override_form = BillingAssociationPriceOverrideForm(
                request.POST,
                instance=override_instance,
            )
            if override_form.is_valid():
                saved_override = override_form.save()
                association_name = (
                    saved_override.association_billing_profile.association_profile.contact.name
                )
                messages.success(
                    request, f'Surcharge association "{association_name}" enregistree.'
                )
                return redirect("scan:scan_billing_settings")
        else:
            messages.error(request, "Action de facturation inconnue.")

    return render(
        request,
        TEMPLATE_SCAN_BILLING_SETTINGS,
        _build_billing_settings_context(
            active="billing_settings",
            profile_form=profile_form,
            service_form=service_form,
            override_form=override_form,
        ),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_billing_equivalence(request):
    _require_superuser(request)
    rule_instance = _selected_instance_from_query(
        request,
        query_key="edit_rule",
        model=ShipmentUnitEquivalenceRule,
    )
    rule_form = ShipmentUnitEquivalenceRuleForm(instance=rule_instance)

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == ACTION_SAVE_EQUIVALENCE_RULE:
            rule_id = (request.POST.get("rule_id") or "").strip()
            rule_instance = (
                get_object_or_404(ShipmentUnitEquivalenceRule, pk=rule_id) if rule_id else None
            )
            rule_form = ShipmentUnitEquivalenceRuleForm(request.POST, instance=rule_instance)
            if rule_form.is_valid():
                saved_rule = rule_form.save()
                messages.success(request, f'Regle d\'equivalence "{saved_rule.label}" enregistree.')
                return redirect("scan:scan_billing_equivalence")
        else:
            messages.error(request, "Action d'equivalence inconnue.")

    return render(
        request,
        TEMPLATE_SCAN_BILLING_EQUIVALENCE,
        _build_billing_equivalence_context(
            active="billing_equivalence",
            rule_form=rule_form,
        ),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_billing_editor(request):
    require_billing_staff_or_superuser(request)
    association_profile = _selected_association_profile(
        request.POST.get("association_profile")
        if request.method == "POST"
        else request.GET.get("association_profile")
    )
    kind = (
        request.POST.get("kind") if request.method == "POST" else request.GET.get("kind")
    ) or BillingDocumentKind.QUOTE
    if kind not in BillingDocumentKind.values:
        kind = BillingDocumentKind.QUOTE
    action = (request.POST.get("action") or "").strip().lower() if request.method == "POST" else ""
    period = _resolved_period(request)
    candidate_rows = []
    draft_document = None
    selected_currency = _selected_document_currency(request, association_profile)
    exchange_rate_resolution = resolve_exchange_rate(
        document_currency=selected_currency,
        base_currency="EUR",
    )
    draft_options_form = _build_draft_options_form(
        request=request,
        action=action,
        selected_currency=selected_currency,
        exchange_rate_resolution=exchange_rate_resolution,
    )

    if association_profile is not None:
        candidate_rows = build_editor_candidates(
            association_profile=association_profile,
            kind=kind,
            period=period,
        )

    if request.method == "POST":
        if action == ACTION_BUILD_DRAFT:
            selected_shipment_ids = [
                int(value) for value in request.POST.getlist("shipment_ids") if value
            ]
            eligible_ids = {row.shipment_id for row in candidate_rows}
            selected_shipment_ids = [
                shipment_id for shipment_id in selected_shipment_ids if shipment_id in eligible_ids
            ]
            if association_profile is None:
                messages.error(request, "Association de facturation introuvable.")
            elif not selected_shipment_ids:
                messages.error(request, "Selectionnez au moins une expedition eligible.")
            elif not draft_options_form.is_valid():
                messages.error(request, "Corrigez les champs devise et taux de change.")
            else:
                manual_lines = []
                manual_label = (request.POST.get("manual_label") or "").strip()
                manual_amount = (request.POST.get("manual_amount") or "").strip()
                if manual_label and manual_amount:
                    manual_lines.append(
                        {
                            "label": manual_label,
                            "description": (request.POST.get("manual_description") or "").strip(),
                            "amount": manual_amount,
                        }
                    )
                selected_currency = draft_options_form.cleaned_data["currency"]
                exchange_rate = draft_options_form.cleaned_data["exchange_rate"]
                if exchange_rate is None:
                    exchange_rate = exchange_rate_resolution.rate
                if exchange_rate is None:
                    draft_options_form.add_error(
                        "exchange_rate",
                        "Saisissez manuellement un taux de change pour cette devise.",
                    )
                    messages.error(request, "Le taux de change doit etre renseigne.")
                else:
                    if not isinstance(exchange_rate, Decimal):
                        exchange_rate = Decimal(str(exchange_rate))
                    draft_document = create_billing_draft(
                        association_profile=association_profile,
                        kind=kind,
                        shipment_ids=selected_shipment_ids,
                        created_by=request.user,
                        manual_lines=manual_lines,
                        currency=selected_currency,
                        exchange_rate=exchange_rate,
                    )
                    messages.success(request, "Brouillon de facturation genere.")
        elif action == ACTION_ISSUE_DOCUMENT:
            document_id = (request.POST.get("document_id") or "").strip()
            if not document_id:
                messages.error(request, "Document a emettre introuvable.")
            else:
                draft_document = get_object_or_404(
                    BillingDocument.objects.select_related("association_profile__contact"),
                    pk=document_id,
                )
                association_profile = draft_document.association_profile
                kind = draft_document.kind
                try:
                    draft_document = issue_billing_document(
                        document=draft_document,
                        invoice_number=request.POST.get("invoice_number"),
                    )
                except ValueError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, "Document de facturation emis.")
                    candidate_rows = build_editor_candidates(
                        association_profile=association_profile,
                        kind=kind,
                        period=period,
                    )

    return render(
        request,
        TEMPLATE_SCAN_BILLING_EDITOR,
        _build_billing_editor_context(
            active="billing_editor",
            association_profile=association_profile,
            kind=kind,
            period=period,
            candidate_rows=candidate_rows,
            draft_document=draft_document,
            draft_options_form=draft_options_form,
            exchange_rate_resolution=exchange_rate_resolution,
        ),
    )
