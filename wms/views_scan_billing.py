from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .billing_permissions import require_billing_staff_or_superuser
from .forms_billing import (
    BillingAssociationPriceOverrideForm,
    BillingComputationProfileForm,
    BillingServiceCatalogItemForm,
    ShipmentUnitEquivalenceRuleForm,
)
from .models import (
    BillingAssociationPriceOverride,
    BillingComputationProfile,
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
@require_http_methods(["GET"])
def scan_billing_editor(request):
    require_billing_staff_or_superuser(request)
    return render(
        request,
        TEMPLATE_SCAN_BILLING_EDITOR,
        {
            "active": "billing_editor",
        },
    )
