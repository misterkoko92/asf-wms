from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import ExpressionWrapper, F, IntegerField, Min, Sum
from django.urls import reverse
from django.utils import timezone

from wms.models import (
    CartonItem,
    Product,
    ProductLot,
    ProductLotStatus,
    RecipientProductPreference,
    RecipientProductPreferenceStatus,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)
from wms.product_category_filters import build_category_filter_context
from wms.recipient_product_preferences import (
    list_effective_recipient_product_preferences,
    list_recipient_product_coverages,
)
from wms.runtime_settings import get_runtime_config
from wms.shipment_helpers import default_shipment_recipient_contact_for_shipper

FILTER_DESTINATION_PARAM = "destination"
FILTER_RECIPIENT_PARAM = "recipient"
FILTER_CATEGORY_PARAM = "category"
FILTER_NEED_STATUS_PARAM = "need_status"
FILTER_PRIORITY_PARAM = "priority"

NEED_STATUS_TO_SERVE = "to_serve"
NEED_STATUS_COVERED = "covered"
NEED_STATUS_REFUSED = "refused"

PRIORITY_CRITICAL = "critical"
PRIORITY_HIGH = "high"
PRIORITY_NORMAL = "normal"
PRIORITY_COVERED = "covered"
PRIORITY_OUT_OF_SCOPE = "out_of_scope"

PRIORITY_ORDER = {
    PRIORITY_CRITICAL: 0,
    PRIORITY_HIGH: 1,
    PRIORITY_NORMAL: 2,
    PRIORITY_COVERED: 3,
    PRIORITY_OUT_OF_SCOPE: 4,
}

PREPARE_ACTIONABLE_PRIORITIES = {
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
}


def build_scan_recipient_needs_context(request, *, as_of=None):
    now = _normalize_as_of(as_of)
    filter_state = _get_filter_state(request)
    category_filter_context = build_category_filter_context(
        selected_category_id=filter_state["category_id"]
    )
    runtime_config = get_runtime_config()

    recipient_organizations = list(
        _build_recipient_organization_queryset(filter_state=filter_state)
    )
    shipper_labels_by_recipient_id = _collect_shipper_labels(recipient_organizations)
    prepare_targets_by_recipient_id = {
        recipient_organization.id: _resolve_prepare_target(
            recipient_organization=recipient_organization
        )
        for recipient_organization in recipient_organizations
    }
    recipient_contact_ids_by_org_id = {
        recipient_organization.id: _recipient_contact_ids(recipient_organization)
        for recipient_organization in recipient_organizations
    }
    active_products = _active_products_for_filter(category_filter_context=category_filter_context)
    explicit_preferences = list(
        RecipientProductPreference.objects.filter(
            recipient_organization__in=recipient_organizations,
        )
        .select_related(
            "recipient_organization__organization",
            "recipient_organization__destination",
            "product__category",
            "category",
        )
        .order_by("recipient_organization_id", "id")
    )
    explicit_product_preferences_by_org_id = defaultdict(list)
    explicit_category_preferences_by_org_id = defaultdict(list)
    for preference in explicit_preferences:
        recipient_organization = getattr(preference, "recipient_organization", None)
        recipient_organization_id = getattr(recipient_organization, "id", None)
        if recipient_organization_id is None:
            continue
        if getattr(preference, "product", None) is not None:
            explicit_product_preferences_by_org_id[recipient_organization_id].append(preference)
        elif getattr(preference, "category", None) is not None:
            explicit_category_preferences_by_org_id[recipient_organization_id].append(preference)

    rows = []
    for recipient_organization in recipient_organizations:
        candidate_products = _collect_candidate_products(
            recipient_organization=recipient_organization,
            explicit_product_preferences=explicit_product_preferences_by_org_id[
                recipient_organization.id
            ],
            explicit_category_preferences=explicit_category_preferences_by_org_id[
                recipient_organization.id
            ],
            active_products=active_products,
            category_paths_by_id=category_filter_context["category_paths_by_id"],
        )
        if not candidate_products:
            continue

        effective_preferences = list_effective_recipient_product_preferences(
            recipient_organization=recipient_organization,
            products=candidate_products,
        )
        actionable_products = []
        for effective_preference in effective_preferences:
            product = getattr(effective_preference, "product", None)
            if product is None:
                continue
            if effective_preference.status in {
                RecipientProductPreferenceStatus.REQUESTED,
                RecipientProductPreferenceStatus.ALLOWED,
            }:
                actionable_products.append(product)
        coverage_by_product_id = {}
        for coverage in list_recipient_product_coverages(
            recipient_organization=recipient_organization,
            products=actionable_products,
            as_of=now,
        ):
            coverage_product = getattr(coverage, "product", None)
            coverage_product_id = getattr(coverage_product, "id", None)
            if coverage_product_id is None:
                continue
            coverage_by_product_id[coverage_product_id] = coverage
        open_shipment_stats_by_product_id = _collect_open_shipment_stats(
            recipient_organization=recipient_organization,
            product_ids=[product.id for product in candidate_products],
            contact_ids=recipient_contact_ids_by_org_id[recipient_organization.id],
        )

        for effective_preference in effective_preferences:
            product = getattr(effective_preference, "product", None)
            if effective_preference.status == "unspecified" or product is None:
                continue
            row = _build_row(
                recipient_organization=recipient_organization,
                effective_preference=effective_preference,
                coverage=coverage_by_product_id.get(product.id),
                open_shipment_stats=open_shipment_stats_by_product_id.get(product.id),
                shipper_labels=shipper_labels_by_recipient_id.get(recipient_organization.id, []),
                prepare_target=prepare_targets_by_recipient_id.get(recipient_organization.id, {}),
                tracking_alert_hours=runtime_config.tracking_alert_hours,
                as_of=now,
            )
            if _row_matches_filters(row=row, filter_state=filter_state):
                rows.append(row)

    _decorate_rows_with_stock_availability(rows)

    rows.sort(
        key=lambda row: (
            row["priority_rank"],
            -row["delay_hours"],
            row["period_deadline_sort_key"],
            -row["remaining_need_sort_value"],
            row["recipient_name"].casefold(),
            row["product_name"].casefold(),
        )
    )

    return {
        "rows": rows,
        "summary_cards": _build_summary_cards(rows),
        "destinations": _build_destination_choices(),
        "recipients": recipient_organizations,
        "destination_id": filter_state["destination_id"],
        "recipient_id": filter_state["recipient_id"],
        "category_id": filter_state["category_id"],
        "need_status": filter_state["need_status"],
        "priority": filter_state["priority"],
        **category_filter_context,
    }


def _normalize_as_of(as_of):
    if as_of is None:
        return timezone.now()
    if timezone.is_naive(as_of):
        return timezone.make_aware(as_of, timezone.get_current_timezone())
    return as_of


def _get_filter_state(request):
    source = request.GET if request.method == "GET" else request.POST
    return {
        "destination_id": (source.get(FILTER_DESTINATION_PARAM) or "").strip(),
        "recipient_id": (source.get(FILTER_RECIPIENT_PARAM) or "").strip(),
        "category_id": (source.get(FILTER_CATEGORY_PARAM) or "").strip(),
        "need_status": (source.get(FILTER_NEED_STATUS_PARAM) or "").strip(),
        "priority": (source.get(FILTER_PRIORITY_PARAM) or "").strip(),
    }


def _build_recipient_organization_queryset(*, filter_state):
    queryset = ShipmentRecipientOrganization.objects.filter(
        is_active=True,
        organization__is_active=True,
        destination__is_active=True,
        validation_status=ShipmentValidationStatus.VALIDATED,
    ).select_related("organization", "destination")
    if filter_state["destination_id"]:
        queryset = queryset.filter(destination_id=filter_state["destination_id"])
    if filter_state["recipient_id"]:
        queryset = queryset.filter(pk=filter_state["recipient_id"])
    return queryset.order_by("destination__city", "organization__name", "id")


def _build_destination_choices():
    return list(
        ShipmentRecipientOrganization.objects.filter(
            is_active=True,
            destination__is_active=True,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        .select_related("destination")
        .order_by("destination__city", "destination__id")
        .values_list("destination__id", "destination__city", "destination__iata_code")
        .distinct()
    )


def _active_products_for_filter(*, category_filter_context):
    products = list(
        Product.objects.filter(is_active=True).select_related("category").order_by("name", "id")
    )
    descendant_ids = set(category_filter_context["descendant_category_ids"])
    if descendant_ids:
        products = [
            product
            for product in products
            if getattr(product, "category_id", None) in descendant_ids
        ]
    return products


def _collect_candidate_products(
    *,
    recipient_organization,
    explicit_product_preferences,
    explicit_category_preferences,
    active_products,
    category_paths_by_id,
):
    candidate_products_by_id = {}
    for preference in explicit_product_preferences:
        product = preference.product
        if product is None or not getattr(product, "is_active", False):
            continue
        candidate_products_by_id[product.id] = product

    for preference in explicit_category_preferences:
        category_id = getattr(preference, "category_id", None)
        if not category_id:
            continue
        prefix_path = category_paths_by_id.get(str(category_id), [])
        if not prefix_path:
            continue
        for product in active_products:
            product_category_id = getattr(product, "category_id", None)
            if not product_category_id:
                continue
            product_path = category_paths_by_id.get(str(product_category_id), [])
            if product_path[: len(prefix_path)] == prefix_path:
                candidate_products_by_id[product.id] = product

    return list(candidate_products_by_id.values())


def _recipient_contact_ids(recipient_organization):
    contact_ids = set(
        ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
            contact__is_active=True,
        ).values_list("contact_id", flat=True)
    )
    if recipient_organization.organization_id:
        contact_ids.add(recipient_organization.organization_id)
    return contact_ids


def _collect_shipper_labels(recipient_organizations):
    links = (
        ShipmentShipperRecipientLink.objects.filter(
            recipient_organization__in=recipient_organizations,
            is_active=True,
            shipper__is_active=True,
            shipper__organization__is_active=True,
        )
        .select_related("shipper__organization")
        .order_by("shipper__organization__name", "id")
    )
    labels_by_recipient_id: dict[int, list[str]] = defaultdict(list)
    for link in links:
        label = link.shipper.organization.name
        recipient_organization_id = getattr(link.recipient_organization, "id", None)
        if recipient_organization_id is None:
            continue
        if label not in labels_by_recipient_id[recipient_organization_id]:
            labels_by_recipient_id[recipient_organization_id].append(label)
    return labels_by_recipient_id


def _resolve_prepare_target(*, recipient_organization):
    links = list(
        ShipmentShipperRecipientLink.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
            shipper__is_active=True,
            shipper__organization__is_active=True,
            shipper__validation_status=ShipmentValidationStatus.VALIDATED,
            shipper__default_contact__is_active=True,
        )
        .select_related("shipper__organization", "shipper__default_contact")
        .order_by("shipper__organization__name", "id")
    )
    shippers_by_id: dict[int, ShipmentShipper] = {}
    for link in links:
        shipper = getattr(link, "shipper", None)
        if shipper is None or not getattr(shipper, "default_contact_id", None):
            continue
        shippers_by_id.setdefault(shipper.id, shipper)
    shippers = list(shippers_by_id.values())
    if not shippers:
        return {
            "shipper_contact_id": None,
            "recipient_contact_id": None,
            "disabled_reason": "Aucun expediteur actif lie a ce destinataire.",
        }
    if len(shippers) > 1:
        return {
            "shipper_contact_id": None,
            "recipient_contact_id": None,
            "disabled_reason": "Plusieurs expediteurs lies: preparation a affiner depuis le dossier.",
        }
    shipper = shippers[0]
    shipper_default_contact = getattr(shipper, "default_contact", None)
    shipper_default_contact_id = getattr(shipper_default_contact, "id", None)
    recipient_contact = default_shipment_recipient_contact_for_shipper(
        shipper=shipper,
        destination=recipient_organization.destination,
    )
    if recipient_contact is None:
        return {
            "shipper_contact_id": shipper_default_contact_id,
            "recipient_contact_id": None,
            "disabled_reason": "Aucun destinataire par defaut disponible pour cet expediteur.",
        }
    return {
        "shipper_contact_id": shipper_default_contact_id,
        "recipient_contact_id": recipient_contact.id,
        "disabled_reason": "",
    }


def _collect_open_shipment_stats(*, recipient_organization, product_ids, contact_ids):
    if not product_ids or not contact_ids:
        return {}
    rows = (
        CartonItem.objects.filter(
            product_lot__product_id__in=product_ids,
            carton__shipment__isnull=False,
            carton__shipment__destination=recipient_organization.destination,
            carton__shipment__recipient_contact_ref_id__in=contact_ids,
            carton__shipment__closed_at__isnull=True,
        )
        .values("product_lot__product_id")
        .annotate(
            oldest_planned_at=Min("carton__shipment__workflow_projection__planned_at"),
        )
    )
    return {
        row["product_lot__product_id"]: {
            "oldest_planned_at": row["oldest_planned_at"],
        }
        for row in rows
    }


def _build_row(
    *,
    recipient_organization,
    effective_preference,
    coverage,
    open_shipment_stats,
    shipper_labels,
    prepare_target,
    tracking_alert_hours,
    as_of,
):
    product = effective_preference.product
    period_end = getattr(coverage, "period_end", None)
    remaining_need = _coalesce_int(getattr(coverage, "remaining_need", None))
    delivered_quantity = _coalesce_int(getattr(coverage, "delivered_quantity", None))
    pipeline_quantity = _coalesce_int(getattr(coverage, "pipeline_quantity", None))
    oldest_planned_at = (open_shipment_stats or {}).get("oldest_planned_at")
    priority, priority_help, delay_hours = _classify_priority(
        status=effective_preference.status,
        remaining_need=remaining_need,
        delivered_quantity=delivered_quantity,
        pipeline_quantity=pipeline_quantity,
        period_end=period_end,
        period_unit=getattr(coverage, "period_unit", None),
        oldest_planned_at=oldest_planned_at,
        tracking_alert_hours=tracking_alert_hours,
        as_of=as_of,
    )
    category = getattr(product, "category", None)
    return {
        "recipient_organization_id": recipient_organization.id,
        "recipient_name": recipient_organization.organization.name,
        "destination_id": recipient_organization.destination_id,
        "destination_label": str(recipient_organization.destination),
        "product_id": product.id,
        "product_name": product.name,
        "category_id": getattr(product, "category_id", None),
        "category_label": str(category) if category is not None else "-",
        "status": effective_preference.status,
        "scope": effective_preference.scope,
        "shipper_labels": shipper_labels,
        "target_quantity": _coalesce_int(getattr(coverage, "target_quantity", None)),
        "delivered_quantity": delivered_quantity,
        "pipeline_quantity": pipeline_quantity,
        "remaining_need": remaining_need,
        "remaining_need_sort_value": remaining_need,
        "period_unit": getattr(coverage, "period_unit", None) or "",
        "period_label": _build_period_label(getattr(coverage, "period_unit", None)),
        "period_end": period_end,
        "period_deadline_label": _build_period_deadline_label(
            period_end=period_end,
            delay_hours=delay_hours,
            as_of=as_of,
        ),
        "period_deadline_sort_key": period_end
        or timezone.make_aware(
            datetime.max.replace(tzinfo=None),
            timezone.get_current_timezone(),
        ),
        "priority": priority,
        "priority_rank": PRIORITY_ORDER[priority],
        "priority_help": priority_help,
        "delay_hours": delay_hours,
        "selection_key": f"{recipient_organization.id}:{product.id}",
        "prepare_shipper_contact_id": prepare_target.get("shipper_contact_id"),
        "prepare_recipient_contact_id": prepare_target.get("recipient_contact_id"),
        "prepare_disabled_reason": prepare_target.get("disabled_reason") or "",
        "prepare_product_code": _build_prepare_product_code(product),
        "prepare_quantity": 0,
        "can_prepare": False,
        "recipient_admin_url": reverse(
            "scan:scan_admin_recipient_organization_detail",
            args=[recipient_organization.id],
        ),
    }


def _coalesce_int(value):
    if value is None:
        return 0
    return int(value)


def _build_prepare_product_code(product):
    sku = (getattr(product, "sku", "") or "").strip()
    if sku:
        return sku
    return (getattr(product, "name", "") or "").strip()


def _collect_available_stock_by_product_ids(product_ids):
    if not product_ids:
        return {}
    available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    rows = (
        ProductLot.objects.filter(
            product_id__in=product_ids,
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand__gt=0,
        )
        .values("product_id")
        .annotate(total_available=Sum(available_expr))
    )
    return {row["product_id"]: max(int(row["total_available"] or 0), 0) for row in rows}


def _stock_availability_tone(*, available_quantity, required_quantity):
    if required_quantity <= 0:
        return "muted"
    ratio = available_quantity / required_quantity
    if ratio < 0.25:
        return "danger"
    if ratio < 0.75:
        return "warning"
    return "success"


def _build_stock_availability_fields(*, available_quantity, required_quantity):
    if required_quantity <= 0:
        return {
            "stock_available_quantity": available_quantity,
            "stock_required_quantity": 0,
            "stock_availability_label": str(available_quantity),
            "stock_availability_tone": "muted",
            "stock_availability_help": "Stock disponible actuel.",
        }
    return {
        "stock_available_quantity": available_quantity,
        "stock_required_quantity": required_quantity,
        "stock_availability_label": f"{available_quantity}/{required_quantity}",
        "stock_availability_tone": _stock_availability_tone(
            available_quantity=available_quantity,
            required_quantity=required_quantity,
        ),
        "stock_availability_help": (
            f"Stock disponible {available_quantity} pour un reste a servir de {required_quantity}."
        ),
    }


def _decorate_rows_with_stock_availability(rows):
    stock_available_by_product_id = _collect_available_stock_by_product_ids(
        {row["product_id"] for row in rows}
    )
    for row in rows:
        available_quantity = stock_available_by_product_id.get(row["product_id"], 0)
        required_quantity = (
            row["remaining_need"] if row["remaining_need"] > 0 else row["target_quantity"]
        )
        row.update(
            _build_stock_availability_fields(
                available_quantity=available_quantity,
                required_quantity=required_quantity,
            )
        )
        prepare_quantity = min(row["remaining_need"], available_quantity)
        row["prepare_quantity"] = prepare_quantity
        if row["priority"] == PRIORITY_COVERED:
            row["prepare_disabled_reason"] = "Besoin deja couvert."
        elif row["priority"] == PRIORITY_OUT_OF_SCOPE:
            row["prepare_disabled_reason"] = "Preference refusee: preparation indisponible."
        elif (
            not row["prepare_disabled_reason"]
            and row["priority"] in PREPARE_ACTIONABLE_PRIORITIES
            and prepare_quantity <= 0
        ):
            row["prepare_disabled_reason"] = "Aucun stock disponible pour cette demande."
        row["can_prepare"] = bool(
            row["priority"] in PREPARE_ACTIONABLE_PRIORITIES
            and row["prepare_shipper_contact_id"]
            and row["prepare_recipient_contact_id"]
            and prepare_quantity > 0
        )


def _classify_priority(
    *,
    status,
    remaining_need,
    delivered_quantity,
    pipeline_quantity,
    period_end,
    period_unit,
    oldest_planned_at,
    tracking_alert_hours,
    as_of,
):
    if status == RecipientProductPreferenceStatus.REFUSED:
        return (
            PRIORITY_OUT_OF_SCOPE,
            "Produit refuse: hors priorisation operationnelle.",
            0.0,
        )

    if remaining_need <= 0:
        return (
            PRIORITY_COVERED,
            (f"Reste a servir 0. Livre {delivered_quantity}, " f"pipeline {pipeline_quantity}."),
            0.0,
        )

    delay_hours = 0.0
    if oldest_planned_at is not None:
        delay_hours = max(
            ((as_of - oldest_planned_at).total_seconds() / 3600.0) - tracking_alert_hours,
            0.0,
        )
    if period_end is not None and period_end <= as_of:
        return (
            PRIORITY_CRITICAL,
            (
                f"Critique: reste a servir {remaining_need}, fin de periode depassee le "
                f"{timezone.localtime(period_end).strftime('%d/%m')}."
            ),
            delay_hours,
        )

    if delay_hours > 0:
        return (
            PRIORITY_CRITICAL,
            (
                f"Critique: reste a servir {remaining_need}, expedition ouverte en retard de "
                f"{delay_hours:.1f}h (seuil SLA {tracking_alert_hours}h)."
            ),
            delay_hours,
        )

    if pipeline_quantity <= 0:
        return (
            PRIORITY_HIGH,
            f"Haute: reste a servir {remaining_need}, aucun pipeline ouvert.",
            delay_hours,
        )

    due_soon_delta = _due_soon_delta(period_unit=period_unit)
    if (
        period_end is not None
        and due_soon_delta is not None
        and period_end - as_of <= due_soon_delta
    ):
        return (
            PRIORITY_HIGH,
            (
                f"Haute: reste a servir {remaining_need}, fin de periode proche le "
                f"{timezone.localtime(period_end).strftime('%d/%m')}."
            ),
            delay_hours,
        )

    return (
        PRIORITY_NORMAL,
        (
            f"Normale: reste a servir {remaining_need}, pipeline {pipeline_quantity}, "
            "pas de retard critique detecte."
        ),
        delay_hours,
    )


def _due_soon_delta(*, period_unit):
    if period_unit == "week":
        return timedelta(hours=48)
    if period_unit == "month":
        return timedelta(days=7)
    return None


def _build_period_deadline_label(*, period_end, delay_hours, as_of):
    if period_end is None:
        return "-"
    if period_end <= as_of:
        return f"Periode depassee le {timezone.localtime(period_end).strftime('%d/%m')}"
    if delay_hours > 0:
        return f"Retard expedition {delay_hours:.1f}h"
    return f"Fin de periode {timezone.localtime(period_end).strftime('%d/%m')}"


def _build_period_label(period_unit):
    if period_unit == "week":
        return "Semaine"
    if period_unit == "month":
        return "Mois"
    return "-"


def _row_matches_filters(*, row, filter_state):
    need_status = filter_state["need_status"]
    if need_status == NEED_STATUS_TO_SERVE and row["priority"] not in {
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_NORMAL,
    }:
        return False
    if need_status == NEED_STATUS_COVERED and row["priority"] != PRIORITY_COVERED:
        return False
    if (
        need_status == NEED_STATUS_REFUSED
        and row["status"] != RecipientProductPreferenceStatus.REFUSED
    ):
        return False

    priority = filter_state["priority"]
    if priority and row["priority"] != priority:
        return False
    return True


def _build_summary_cards(rows):
    urgent_rows = [row for row in rows if row["priority"] in {PRIORITY_CRITICAL, PRIORITY_HIGH}]
    urgent_recipient_ids = {row["recipient_organization_id"] for row in urgent_rows}
    return [
        {
            "key": "priority_rows",
            "label": "Lignes prioritaires",
            "value": len(urgent_rows),
        },
        {
            "key": "urgent_recipients",
            "label": "Destinataires urgents",
            "value": len(urgent_recipient_ids),
        },
        {
            "key": "remaining_need",
            "label": "Reste a servir",
            "value": sum(row["remaining_need"] for row in rows),
        },
        {
            "key": "covered_rows",
            "label": "Lignes couvertes",
            "value": sum(1 for row in rows if row["priority"] == PRIORITY_COVERED),
        },
    ]
