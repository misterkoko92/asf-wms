from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import Count, F, IntegerField, Max, Q, Sum, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.http import require_http_methods

from .models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    Carton,
    CartonStatus,
    CartonStatusEvent,
    Destination,
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
    ShipmentUnitEquivalenceRule,
)
from .runtime_settings import get_runtime_config
from .scan_permissions import user_is_preparateur
from .unit_equivalence import ShipmentUnitInput, resolve_shipment_unit_count
from .view_permissions import scan_staff_required

TEMPLATE_DASHBOARD = "scan/dashboard.html"
ACTIVE_DASHBOARD = "dashboard"

PERIOD_TODAY = "today"
PERIOD_7D = "7d"
PERIOD_30D = "30d"
PERIOD_WEEK = "week"
DEFAULT_PERIOD = PERIOD_WEEK
PERIOD_CHOICES = (
    (PERIOD_TODAY, _lazy("Aujourd'hui")),
    (PERIOD_7D, _lazy("7 jours")),
    (PERIOD_30D, _lazy("30 jours")),
    (PERIOD_WEEK, _lazy("Semaine en cours")),
)

SHIPMENT_STATUS_ORDER = (
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
)


@scan_staff_required
@require_http_methods(["GET"])
def scan_root(request):
    if user_is_preparateur(request.user):
        return redirect("scan:scan_pack")
    return redirect("scan:scan_dashboard")


def _period_start(period_key):
    now = timezone.now()
    tz = timezone.get_current_timezone()
    if period_key == PERIOD_TODAY:
        return timezone.make_aware(
            datetime.combine(timezone.localdate(), time.min),
            tz,
        )
    if period_key == PERIOD_7D:
        return now - timedelta(days=7)
    if period_key == PERIOD_30D:
        return now - timedelta(days=30)
    if period_key == PERIOD_WEEK:
        today = timezone.localdate()
        iso_year, iso_week, _ = today.isocalendar()
        week_start = date.fromisocalendar(iso_year, iso_week, 1)
        return timezone.make_aware(datetime.combine(week_start, time.min), tz)
    return now - timedelta(days=7)


def _normalize_period(raw_value):
    value = (raw_value or "").strip().lower()
    allowed = {choice[0] for choice in PERIOD_CHOICES}
    if value in allowed:
        return value
    return DEFAULT_PERIOD


def _current_week_bounds():
    today = timezone.localdate()
    iso_year, iso_week, _ = today.isocalendar()
    week_start = date.fromisocalendar(iso_year, iso_week, 1)
    return week_start, week_start + timedelta(days=7)


def _current_week_date_bounds():
    start_date, end_exclusive = _current_week_bounds()
    return start_date, end_exclusive - timedelta(days=1)


def _parse_date_window(start_raw, end_raw):
    default_start, default_end = _current_week_date_bounds()
    start_date = parse_date((start_raw or "").strip()) or default_start
    end_date = parse_date((end_raw or "").strip()) or default_end
    if start_date > end_date:
        start_date, end_date = default_start, default_end

    tz = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_exclusive = timezone.make_aware(
        datetime.combine(end_date + timedelta(days=1), time.min),
        tz,
    )
    return start_date, end_date, start_at, end_exclusive


def _build_card(*, label, value, help_text, url, tone="neutral"):
    return {
        "label": label,
        "value": value,
        "help": help_text,
        "url": url,
        "tone": tone,
    }


def _annotate_tracking_dates(queryset):
    return queryset.annotate(
        planned_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.PLANNED),
        ),
        boarding_ok_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.BOARDING_OK),
        ),
        received_correspondent_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT),
        ),
        received_recipient_at=Max(
            "tracking_events__created_at",
            filter=Q(tracking_events__status=ShipmentTrackingStatus.RECEIVED_RECIPIENT),
        ),
    )


def _status_count_map(shipments_qs):
    status_counts = {
        item["status"]: item["total"]
        for item in shipments_qs.values("status").annotate(total=Count("id"))
    }
    return {status: status_counts.get(status, 0) for status in SHIPMENT_STATUS_ORDER}


def _build_chart_rows(status_count_map):
    total = sum(status_count_map.values())
    rows = []
    label_map = dict(ShipmentStatus.choices)
    for status in SHIPMENT_STATUS_ORDER:
        count = status_count_map.get(status, 0)
        percent = round((count / total) * 100, 1) if total else 0
        rows.append(
            {
                "status": status,
                "label": label_map.get(status, status),
                "count": count,
                "percent": percent,
            }
        )
    return rows, total


def _normalize_shipment_status(raw_value):
    value = (raw_value or "").strip()
    allowed = {choice[0] for choice in ShipmentStatus.choices}
    if value in allowed:
        return value
    return ""


def _build_destination_label(*, destination, fallback=""):
    if destination is not None and destination.iata_code and destination.city:
        return f"{destination.iata_code} - {destination.city}"
    if destination is not None and destination.iata_code:
        return destination.iata_code
    if destination is not None and destination.city:
        return destination.city
    if fallback:
        return fallback
    return "-"


def _build_shipment_equivalence_items(shipment):
    items = []
    for carton in shipment.carton_set.all():
        for carton_item in carton.cartonitem_set.all():
            items.append(
                ShipmentUnitInput(
                    product=carton_item.product_lot.product,
                    quantity=carton_item.quantity,
                )
            )
    return items


def _build_destination_chart_rows(shipments, *, equivalence_rules):
    buckets = defaultdict(
        lambda: {
            "destination_label": "-",
            "shipment_count": 0,
            "equivalent_units": 0,
        }
    )

    for shipment in shipments:
        label = _build_destination_label(
            destination=shipment.destination,
            fallback=shipment.destination_address,
        )
        bucket = buckets[label]
        bucket["destination_label"] = label
        bucket["shipment_count"] += 1
        bucket["equivalent_units"] += resolve_shipment_unit_count(
            items=_build_shipment_equivalence_items(shipment),
            rules=equivalence_rules,
        )

    rows = sorted(
        buckets.values(),
        key=lambda item: (
            -item["shipment_count"],
            -item["equivalent_units"],
            item["destination_label"],
        ),
    )
    total_shipments = sum(row["shipment_count"] for row in rows)
    total_equivalent_units = sum(row["equivalent_units"] for row in rows)
    for row in rows:
        row["shipment_percent"] = (
            round((row["shipment_count"] / total_shipments) * 100, 1) if total_shipments else 0
        )
        row["equivalent_percent"] = (
            round((row["equivalent_units"] / total_equivalent_units) * 100, 1)
            if total_equivalent_units
            else 0
        )
        # Keep the legacy template rendering until the dedicated template task rewires the card.
        row["label"] = row["destination_label"]
        row["count"] = row["shipment_count"]
        row["percent"] = row["shipment_percent"]
    return rows, total_shipments, total_equivalent_units


def _stock_snapshot(*, low_stock_threshold):
    lot_available_expr = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=IntegerField(),
    )
    product_available_expr = ExpressionWrapper(
        F("productlot__quantity_on_hand") - F("productlot__quantity_reserved"),
        output_field=IntegerField(),
    )
    active_products = Product.objects.filter(is_active=True)
    available_lots = ProductLot.objects.filter(
        status=ProductLotStatus.AVAILABLE,
        quantity_on_hand__gt=0,
    )
    total_available_qty = available_lots.aggregate(total=Sum(lot_available_expr))["total"] or 0

    products_with_qty = active_products.annotate(
        available_qty=Coalesce(
            Sum(
                product_available_expr,
                filter=Q(productlot__status=ProductLotStatus.AVAILABLE),
            ),
            Value(0),
            output_field=IntegerField(),
        )
    )
    low_stock_qs = products_with_qty.filter(available_qty__lt=low_stock_threshold).order_by(
        "available_qty", "name"
    )

    return {
        "active_products_count": active_products.count(),
        "available_lots_count": available_lots.count(),
        "total_available_qty": total_available_qty,
        "low_stock_count": low_stock_qs.count(),
        "low_stock_rows": list(low_stock_qs.values("name", "sku", "available_qty")[:10]),
    }


def _email_queue_snapshot(*, processing_timeout_seconds):
    queue_qs = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source="wms.email",
        event_type="send_email",
    )
    status_counts = {
        item["status"]: item["total"]
        for item in queue_qs.values("status").annotate(total=Count("id"))
    }
    stale_cutoff = timezone.now() - timedelta(seconds=processing_timeout_seconds)
    stale_processing_count = queue_qs.filter(
        status=IntegrationStatus.PROCESSING,
        processed_at__lte=stale_cutoff,
    ).count()

    return {
        "pending_count": status_counts.get(IntegrationStatus.PENDING, 0),
        "processing_count": status_counts.get(IntegrationStatus.PROCESSING, 0),
        "failed_count": status_counts.get(IntegrationStatus.FAILED, 0),
        "processed_count": status_counts.get(IntegrationStatus.PROCESSED, 0),
        "stale_processing_count": stale_processing_count,
    }


def _workflow_blockage_snapshot(shipments_scope, *, workflow_blockage_hours):
    cutoff = timezone.now() - timedelta(hours=workflow_blockage_hours)
    return {
        "stale_preparing_shipments_count": shipments_scope.filter(
            status__in=[ShipmentStatus.DRAFT, ShipmentStatus.PICKING],
            created_at__lt=cutoff,
            closed_at__isnull=True,
        ).count(),
        "stale_unplanned_orders_count": Order.objects.filter(
            review_status=OrderReviewStatus.APPROVED,
            shipment__isnull=True,
            created_at__lt=cutoff,
        ).count(),
        "open_delivered_cases_count": shipments_scope.filter(
            status=ShipmentStatus.DELIVERED,
            closed_at__isnull=True,
        ).count(),
        "open_disputed_cases_count": shipments_scope.filter(
            is_disputed=True,
            closed_at__isnull=True,
        ).count(),
    }


def _hours_between(start_at, end_at):
    if start_at is None or end_at is None:
        return None
    if end_at < start_at:
        return 0.0
    return (end_at - start_at).total_seconds() / 3600


def _build_sla_rows(shipments_with_tracking, *, tracking_alert_hours):
    stage_definitions = (
        {
            "label": _("Planifié -> OK mise à bord"),
            "start": "planned_at",
            "end": "boarding_ok_at",
            "target_hours": tracking_alert_hours,
        },
        {
            "label": _("OK mise à bord -> Reçu escale"),
            "start": "boarding_ok_at",
            "end": "received_correspondent_at",
            "target_hours": tracking_alert_hours,
        },
        {
            "label": _("Reçu escale -> Livré"),
            "start": "received_correspondent_at",
            "end": "received_recipient_at",
            "target_hours": tracking_alert_hours,
        },
        {
            "label": _("Planifié -> Livré"),
            "start": "planned_at",
            "end": "received_recipient_at",
            "target_hours": tracking_alert_hours * 3,
        },
    )
    rows = list(
        shipments_with_tracking.values(
            "planned_at",
            "boarding_ok_at",
            "received_correspondent_at",
            "received_recipient_at",
        )
    )
    sla_rows = []
    for stage in stage_definitions:
        durations = []
        for row in rows:
            duration_hours = _hours_between(row[stage["start"]], row[stage["end"]])
            if duration_hours is None:
                continue
            durations.append(duration_hours)
        completed_count = len(durations)
        breach_count = sum(
            1 for duration_hours in durations if duration_hours > stage["target_hours"]
        )
        average_hours = round(sum(durations) / completed_count, 1) if durations else None
        max_hours = round(max(durations), 1) if durations else None
        sla_rows.append(
            {
                "label": stage["label"],
                "target_hours": stage["target_hours"],
                "completed_count": completed_count,
                "breach_count": breach_count,
                "average_hours": average_hours,
                "max_hours": max_hours,
            }
        )
    return sla_rows


@scan_staff_required
@require_http_methods(["GET"])
def scan_dashboard(request):
    runtime_config = get_runtime_config()
    low_stock_threshold = runtime_config.low_stock_threshold
    tracking_alert_hours = runtime_config.tracking_alert_hours
    workflow_blockage_hours = runtime_config.workflow_blockage_hours
    queue_processing_timeout_seconds = runtime_config.email_queue_processing_timeout_seconds

    period = _normalize_period(request.GET.get("period"))
    period_start = _period_start(period)
    kpi_start_date, kpi_end_date, kpi_start_at, kpi_end_exclusive = _parse_date_window(
        request.GET.get("kpi_start"),
        request.GET.get("kpi_end"),
    )
    chart_start_date, chart_end_date, chart_start_at, chart_end_exclusive = _parse_date_window(
        request.GET.get("chart_start") or request.GET.get("kpi_start"),
        request.GET.get("chart_end") or request.GET.get("kpi_end"),
    )
    shipment_status = _normalize_shipment_status(request.GET.get("shipment_status"))

    destinations = Destination.objects.filter(is_active=True).order_by("city")
    destination_raw = (request.GET.get("destination") or "").strip()
    selected_destination = None
    if destination_raw:
        selected_destination = destinations.filter(pk=destination_raw).first()

    shipments_scope = Shipment.objects.filter(archived_at__isnull=True)
    if selected_destination:
        shipments_scope = shipments_scope.filter(destination=selected_destination)

    shipments_with_tracking = _annotate_tracking_dates(shipments_scope)
    status_map = _status_count_map(shipments_scope)
    chart_shipments_qs = Shipment.objects.filter(
        archived_at__isnull=True,
        created_at__gte=chart_start_at,
        created_at__lt=chart_end_exclusive,
    )
    if selected_destination:
        chart_shipments_qs = chart_shipments_qs.filter(destination=selected_destination)
    if shipment_status:
        chart_shipments_qs = chart_shipments_qs.filter(status=shipment_status)
    chart_shipments = list(
        chart_shipments_qs.select_related("destination").prefetch_related(
            "carton_set__cartonitem_set__product_lot__product__category__parent"
        )
    )
    equivalence_rules = list(
        ShipmentUnitEquivalenceRule.objects.filter(is_active=True).select_related(
            "category",
            "category__parent",
        )
    )
    chart_rows, shipments_total, shipment_equivalent_total = _build_destination_chart_rows(
        chart_shipments,
        equivalence_rules=equivalence_rules,
    )

    week_start, week_end = _current_week_bounds()
    in_transit_count = (
        status_map.get(ShipmentStatus.PLANNED, 0)
        + status_map.get(ShipmentStatus.SHIPPED, 0)
        + status_map.get(ShipmentStatus.RECEIVED_CORRESPONDENT, 0)
    )

    alert_cutoff = timezone.now() - timedelta(hours=tracking_alert_hours)
    planned_alert_count = shipments_with_tracking.filter(
        closed_at__isnull=True,
        status=ShipmentStatus.PLANNED,
        planned_at__lt=alert_cutoff,
        boarding_ok_at__isnull=True,
    ).count()
    shipped_alert_count = shipments_with_tracking.filter(
        closed_at__isnull=True,
        status=ShipmentStatus.SHIPPED,
        boarding_ok_at__lt=alert_cutoff,
        received_correspondent_at__isnull=True,
    ).count()
    correspondent_alert_count = shipments_with_tracking.filter(
        closed_at__isnull=True,
        status=ShipmentStatus.RECEIVED_CORRESPONDENT,
        received_correspondent_at__lt=alert_cutoff,
        received_recipient_at__isnull=True,
    ).count()
    closable_count = shipments_with_tracking.filter(
        closed_at__isnull=True,
        is_disputed=False,
        status=ShipmentStatus.DELIVERED,
        planned_at__isnull=False,
        boarding_ok_at__isnull=False,
        received_correspondent_at__isnull=False,
        received_recipient_at__isnull=False,
    ).count()

    period_shipments_qs = shipments_scope.filter(created_at__gte=period_start)
    activity_cards = [
        _build_card(
            label=_("Expéditions créées"),
            value=period_shipments_qs.count(),
            help_text=_("Création sur la période sélectionnée."),
            url=reverse("scan:scan_shipments_ready"),
        ),
        _build_card(
            label=_("Colis créés"),
            value=Carton.objects.filter(created_at__gte=period_start).count(),
            help_text=_("Tous colis créés sur la période."),
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label=_("Réceptions créées"),
            value=Receipt.objects.filter(created_at__gte=period_start).count(),
            help_text=_("Tous types de réception."),
            url=reverse("scan:scan_receipts_view"),
        ),
        _build_card(
            label=_("Commandes créées"),
            value=Order.objects.filter(created_at__gte=period_start).count(),
            help_text=_("Demandes créées sur la période."),
            url=reverse("scan:scan_orders_view"),
        ),
    ]

    kpi_cards = [
        _build_card(
            label=_("Nb Commandes reçues"),
            value=Order.objects.filter(
                created_at__gte=kpi_start_at,
                created_at__lt=kpi_end_exclusive,
            ).count(),
            help_text=_("Commandes créées sur la période."),
            url=reverse("scan:scan_orders_view"),
        ),
        _build_card(
            label=_("Nb commandes en traitement"),
            value=Order.objects.filter(
                created_at__gte=kpi_start_at,
                created_at__lt=kpi_end_exclusive,
                status__in=[OrderStatus.RESERVED, OrderStatus.PREPARING],
            ).count(),
            help_text=_("Commandes réservées ou en préparation sur la période."),
            url=reverse("scan:scan_orders_view"),
        ),
        _build_card(
            label=_("Nb commandes à valider / corriger"),
            value=Order.objects.filter(
                created_at__gte=kpi_start_at,
                created_at__lt=kpi_end_exclusive,
                review_status__in=[
                    OrderReviewStatus.PENDING,
                    OrderReviewStatus.CHANGES_REQUESTED,
                ],
            ).count(),
            help_text=_("Commandes en attente de revue ASF ou à corriger."),
            url=reverse("scan:scan_orders_view"),
        ),
        _build_card(
            label=_("Nb Colis créés"),
            value=Carton.objects.filter(
                created_at__gte=kpi_start_at,
                created_at__lt=kpi_end_exclusive,
            ).count(),
            help_text=_("Colis créés sur la période."),
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label=_("Nb Colis affectés"),
            value=CartonStatusEvent.objects.filter(
                created_at__gte=kpi_start_at,
                created_at__lt=kpi_end_exclusive,
                new_status=CartonStatus.ASSIGNED,
            )
            .values("carton_id")
            .distinct()
            .count(),
            help_text=_("Transitions vers le statut Affecté sur la période."),
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label=_("Nb Expéditions prêtes"),
            value=Shipment.objects.filter(
                ready_at__gte=kpi_start_at,
                ready_at__lt=kpi_end_exclusive,
            ).count(),
            help_text=_("Expéditions passées à l'état prêt à planifier."),
            url=reverse("scan:scan_shipments_ready"),
        ),
    ]

    shipment_cards = [
        _build_card(
            label=_("Brouillons"),
            value=shipments_scope.filter(
                status=ShipmentStatus.DRAFT,
                reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX,
            ).count(),
            help_text=_("Brouillons temporaires EXP-TEMP-XX."),
            url=reverse("scan:scan_shipments_ready"),
            tone="warn",
        ),
        _build_card(
            label=_("En cours"),
            value=status_map.get(ShipmentStatus.PICKING, 0),
            help_text=_("Expéditions non totalement étiquetées."),
            url=reverse("scan:scan_shipments_ready"),
        ),
        _build_card(
            label=_("Prêtes"),
            value=status_map.get(ShipmentStatus.PACKED, 0),
            help_text=_("Toutes étiquetées, prêtes au planning."),
            url=reverse("scan:scan_shipments_ready"),
            tone="success",
        ),
        _build_card(
            label=_("Planifiées (semaine)"),
            value=shipments_with_tracking.filter(
                status=ShipmentStatus.PLANNED,
                planned_at__date__gte=week_start,
                planned_at__date__lt=week_end,
            ).count(),
            help_text=_("Date du statut Planifié sur semaine courante."),
            url=reverse("scan:scan_shipments_tracking"),
        ),
        _build_card(
            label=_("En transit"),
            value=in_transit_count,
            help_text=_("Planifié + Expédié + Reçu escale."),
            url=reverse("scan:scan_shipments_tracking"),
        ),
        _build_card(
            label=_("Litiges ouverts"),
            value=shipments_scope.filter(
                is_disputed=True,
                closed_at__isnull=True,
            ).count(),
            help_text=_("Expéditions bloquées à traiter."),
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger",
        ),
    ]

    cartons_scope = Carton.objects.all()
    assigned_scope = cartons_scope.filter(status=CartonStatus.ASSIGNED)
    labeled_scope = cartons_scope.filter(status=CartonStatus.LABELED)
    shipped_scope = cartons_scope.filter(status=CartonStatus.SHIPPED)
    if selected_destination:
        assigned_scope = assigned_scope.filter(shipment__destination=selected_destination)
        labeled_scope = labeled_scope.filter(shipment__destination=selected_destination)
        shipped_scope = shipped_scope.filter(shipment__destination=selected_destination)

    carton_cards = [
        _build_card(
            label=_("En préparation"),
            value=cartons_scope.filter(status=CartonStatus.PICKING).count(),
            help_text=_("Colis en cours de préparation."),
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label=_("Prêts non affectés"),
            value=cartons_scope.filter(
                status=CartonStatus.PACKED,
                shipment__isnull=True,
            ).count(),
            help_text=_("Disponibles pour expédition."),
            url=reverse("scan:scan_cartons_ready"),
            tone="warn",
        ),
        _build_card(
            label=_("Affectés non étiquetés"),
            value=assigned_scope.count(),
            help_text=_("Affectés mais pas encore étiquetés."),
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label=_("Étiquetés"),
            value=labeled_scope.count(),
            help_text=_("Colis étiquetés prêts au départ."),
            url=reverse("scan:scan_cartons_ready"),
            tone="success",
        ),
        _build_card(
            label=_("Colis expédiés"),
            value=shipped_scope.count(),
            help_text=_("Sortis après l'étape OK mise à bord."),
            url=reverse("scan:scan_cartons_ready"),
        ),
    ]

    stock_snapshot = _stock_snapshot(low_stock_threshold=low_stock_threshold)
    stock_cards = [
        _build_card(
            label=_("Produits actifs"),
            value=stock_snapshot["active_products_count"],
            help_text=_("Produits actifs catalogués."),
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label=_("Lots disponibles"),
            value=stock_snapshot["available_lots_count"],
            help_text=_("Lots avec stock disponible."),
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label=_("Quantité disponible"),
            value=stock_snapshot["total_available_qty"],
            help_text=_("Somme des quantités disponibles."),
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label=_("Stock bas (< %(threshold)s)") % {"threshold": low_stock_threshold},
            value=stock_snapshot["low_stock_count"],
            help_text=_("Produits sous le seuil global."),
            url=reverse("scan:scan_stock"),
            tone="danger",
        ),
    ]

    flow_cards = [
        _build_card(
            label=_("Réceptions en attente"),
            value=Receipt.objects.filter(status=ReceiptStatus.DRAFT).count(),
            help_text=_("Réceptions non finalisées."),
            url=reverse("scan:scan_receipts_view"),
            tone="warn",
        ),
        _build_card(
            label=_("Cmd en attente de validation"),
            value=Order.objects.filter(review_status=OrderReviewStatus.PENDING).count(),
            help_text=_("Demandes à valider."),
            url=reverse("scan:scan_orders_view"),
        ),
        _build_card(
            label=_("Cmd à modifier"),
            value=Order.objects.filter(review_status=OrderReviewStatus.CHANGES_REQUESTED).count(),
            help_text=_("Retours en correction."),
            url=reverse("scan:scan_orders_view"),
            tone="warn",
        ),
        _build_card(
            label=_("Cmd validées sans expédition"),
            value=Order.objects.filter(
                review_status=OrderReviewStatus.APPROVED,
                shipment__isnull=True,
            ).count(),
            help_text=_("Validées, en attente de création d'expédition."),
            url=reverse("scan:scan_orders_view"),
        ),
    ]

    tracking_cards = [
        _build_card(
            label=_("Planifiées sans mise à bord >%(hours)sh") % {"hours": tracking_alert_hours},
            value=planned_alert_count,
            help_text=_("Sans étape OK mise à bord depuis %(hours)sh.")
            % {"hours": tracking_alert_hours},
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if planned_alert_count else "success",
        ),
        _build_card(
            label=_("Expédiées sans reçu escale >%(hours)sh") % {"hours": tracking_alert_hours},
            value=shipped_alert_count,
            help_text=_("Sans confirmation correspondant depuis %(hours)sh.")
            % {"hours": tracking_alert_hours},
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if shipped_alert_count else "success",
        ),
        _build_card(
            label=_("Reçu escale sans livraison >%(hours)sh") % {"hours": tracking_alert_hours},
            value=correspondent_alert_count,
            help_text=_("Sans confirmation destinataire depuis %(hours)sh.")
            % {"hours": tracking_alert_hours},
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if correspondent_alert_count else "success",
        ),
        _build_card(
            label=_("Dossiers clôturables"),
            value=closable_count,
            help_text=_("Toutes étapes complétées, dossier clos possible."),
            url=reverse("scan:scan_shipments_tracking"),
            tone="success" if closable_count else "neutral",
        ),
    ]

    email_queue_snapshot = _email_queue_snapshot(
        processing_timeout_seconds=queue_processing_timeout_seconds
    )
    technical_cards = [
        _build_card(
            label=_("Queue email en attente"),
            value=email_queue_snapshot["pending_count"],
            help_text=_("Événements en file d'attente à traiter."),
            url=reverse("scan:scan_dashboard"),
            tone="warn" if email_queue_snapshot["pending_count"] else "success",
        ),
        _build_card(
            label=_("Queue email en traitement"),
            value=email_queue_snapshot["processing_count"],
            help_text=_("Événements claimés en cours d'envoi."),
            url=reverse("scan:scan_dashboard"),
        ),
        _build_card(
            label=_("Queue email en échec"),
            value=email_queue_snapshot["failed_count"],
            help_text=_("Événements nécessitant investigation/replay."),
            url=reverse("scan:scan_dashboard"),
            tone="danger" if email_queue_snapshot["failed_count"] else "success",
        ),
        _build_card(
            label=_("Queue email bloquée (timeout)"),
            value=email_queue_snapshot["stale_processing_count"],
            help_text=(
                _("Événements processing au-delà du timeout (%(seconds)ss).")
                % {"seconds": queue_processing_timeout_seconds}
            ),
            url=reverse("scan:scan_dashboard"),
            tone="danger" if email_queue_snapshot["stale_processing_count"] else "success",
        ),
    ]

    workflow_blockage_snapshot = _workflow_blockage_snapshot(
        shipments_scope,
        workflow_blockage_hours=workflow_blockage_hours,
    )
    workflow_blockage_cards = [
        _build_card(
            label=_("Expéditions Création/En cours >%(hours)sh")
            % {"hours": workflow_blockage_hours},
            value=workflow_blockage_snapshot["stale_preparing_shipments_count"],
            help_text=_("Brouillons/En cours anciens à débloquer."),
            url=reverse("scan:scan_shipments_ready"),
            tone=(
                "danger"
                if workflow_blockage_snapshot["stale_preparing_shipments_count"]
                else "success"
            ),
        ),
        _build_card(
            label=_("Cmd validées sans expédition >%(hours)sh")
            % {"hours": workflow_blockage_hours},
            value=workflow_blockage_snapshot["stale_unplanned_orders_count"],
            help_text=_("Commandes approuvées à convertir en expéditions."),
            url=reverse("scan:scan_orders_view"),
            tone=(
                "danger"
                if workflow_blockage_snapshot["stale_unplanned_orders_count"]
                else "success"
            ),
        ),
        _build_card(
            label=_("Dossiers livrés non clos"),
            value=workflow_blockage_snapshot["open_delivered_cases_count"],
            help_text=_("Livrés mais non clôturés."),
            url=reverse("scan:scan_shipments_tracking"),
            tone=(
                "warn" if workflow_blockage_snapshot["open_delivered_cases_count"] else "success"
            ),
        ),
        _build_card(
            label=_("Dossiers en litige ouverts"),
            value=workflow_blockage_snapshot["open_disputed_cases_count"],
            help_text=_("Blocages opérationnels à traiter."),
            url=reverse("scan:scan_shipments_tracking"),
            tone=(
                "danger" if workflow_blockage_snapshot["open_disputed_cases_count"] else "success"
            ),
        ),
    ]

    sla_rows = _build_sla_rows(
        shipments_with_tracking.filter(status__in=list(SHIPMENT_STATUS_ORDER)[3:]),
        tracking_alert_hours=tracking_alert_hours,
    )
    sla_cards = [
        _build_card(
            label=_("%(label)s >%(hours)sh")
            % {"label": row["label"], "hours": row["target_hours"]},
            value=f"{row['breach_count']} / {row['completed_count']}",
            help_text=(
                _("Aucune expédition complétée sur ce segment.")
                if row["completed_count"] == 0
                else (
                    _("Moyenne %(average)sh, max %(max)sh.")
                    % {"average": row["average_hours"], "max": row["max_hours"]}
                )
            ),
            url=reverse("scan:scan_shipments_tracking"),
            tone=(
                "neutral"
                if row["completed_count"] == 0
                else ("danger" if row["breach_count"] else "success")
            ),
        )
        for row in sla_rows
    ]

    period_label_map = dict(PERIOD_CHOICES)
    context = {
        "active": ACTIVE_DASHBOARD,
        "period": period,
        "period_choices": PERIOD_CHOICES,
        "period_label": period_label_map.get(period, ""),
        "destination_id": str(selected_destination.id) if selected_destination else "",
        "destinations": destinations,
        "selected_destination": selected_destination,
        "kpi_start": kpi_start_date.isoformat(),
        "kpi_end": kpi_end_date.isoformat(),
        "kpi_cards": kpi_cards,
        "chart_start": chart_start_date.isoformat(),
        "chart_end": chart_end_date.isoformat(),
        "shipment_status": shipment_status,
        "chart_status_choices": ShipmentStatus.choices,
        "activity_cards": activity_cards,
        "shipment_cards": shipment_cards,
        "carton_cards": carton_cards,
        "stock_cards": stock_cards,
        "flow_cards": flow_cards,
        "tracking_cards": tracking_cards,
        "technical_cards": technical_cards,
        "workflow_blockage_cards": workflow_blockage_cards,
        "sla_cards": sla_cards,
        "low_stock_rows": stock_snapshot["low_stock_rows"],
        "low_stock_threshold": low_stock_threshold,
        "tracking_alert_hours": tracking_alert_hours,
        "workflow_blockage_hours": workflow_blockage_hours,
        "shipment_chart_rows": chart_rows,
        "shipments_total": shipments_total,
        "shipment_equivalent_total": shipment_equivalent_total,
    }
    return render(request, TEMPLATE_DASHBOARD, context)
