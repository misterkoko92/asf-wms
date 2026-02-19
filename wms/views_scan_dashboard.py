from datetime import date, datetime, time, timedelta

from django.db.models import Count, F, IntegerField, Max, Q, Sum, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    Carton,
    CartonStatus,
    Destination,
    Order,
    OrderReviewStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptStatus,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
)
from .view_permissions import scan_staff_required

TEMPLATE_DASHBOARD = "scan/dashboard.html"
ACTIVE_DASHBOARD = "dashboard"

LOW_STOCK_THRESHOLD = 20
TRACKING_ALERT_HOURS = 72

PERIOD_TODAY = "today"
PERIOD_7D = "7d"
PERIOD_30D = "30d"
PERIOD_WEEK = "week"
DEFAULT_PERIOD = PERIOD_WEEK
PERIOD_CHOICES = (
    (PERIOD_TODAY, "Aujourd'hui"),
    (PERIOD_7D, "7 jours"),
    (PERIOD_30D, "30 jours"),
    (PERIOD_WEEK, "Semaine en cours"),
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
            filter=Q(
                tracking_events__status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
            ),
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
    return {
        status: status_counts.get(status, 0)
        for status in SHIPMENT_STATUS_ORDER
    }


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


def _stock_snapshot():
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
    total_available_qty = (
        available_lots.aggregate(total=Sum(lot_available_expr))["total"] or 0
    )

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
    low_stock_qs = products_with_qty.filter(
        available_qty__lt=LOW_STOCK_THRESHOLD
    ).order_by("available_qty", "name")

    return {
        "active_products_count": active_products.count(),
        "available_lots_count": available_lots.count(),
        "total_available_qty": total_available_qty,
        "low_stock_count": low_stock_qs.count(),
        "low_stock_rows": list(
            low_stock_qs.values("name", "sku", "available_qty")[:10]
        ),
    }


@scan_staff_required
@require_http_methods(["GET"])
def scan_dashboard(request):
    period = _normalize_period(request.GET.get("period"))
    period_start = _period_start(period)

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
    chart_rows, shipments_total = _build_chart_rows(status_map)

    week_start, week_end = _current_week_bounds()
    in_transit_count = (
        status_map.get(ShipmentStatus.PLANNED, 0)
        + status_map.get(ShipmentStatus.SHIPPED, 0)
        + status_map.get(ShipmentStatus.RECEIVED_CORRESPONDENT, 0)
    )

    alert_cutoff = timezone.now() - timedelta(hours=TRACKING_ALERT_HOURS)
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
            label="Expéditions créées",
            value=period_shipments_qs.count(),
            help_text="Création sur la période sélectionnée.",
            url=reverse("scan:scan_shipments_ready"),
        ),
        _build_card(
            label="Colis créés",
            value=Carton.objects.filter(created_at__gte=period_start).count(),
            help_text="Tous colis créés sur la période.",
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label="Réceptions créées",
            value=Receipt.objects.filter(created_at__gte=period_start).count(),
            help_text="Tous types de réception.",
            url=reverse("scan:scan_receipts_view"),
        ),
        _build_card(
            label="Commandes créées",
            value=Order.objects.filter(created_at__gte=period_start).count(),
            help_text="Demandes créées sur la période.",
            url=reverse("scan:scan_orders_view"),
        ),
    ]

    shipment_cards = [
        _build_card(
            label="Brouillons",
            value=shipments_scope.filter(
                status=ShipmentStatus.DRAFT,
                reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX,
            ).count(),
            help_text="Brouillons temporaires EXP-TEMP-XX.",
            url=reverse("scan:scan_shipments_ready"),
            tone="warn",
        ),
        _build_card(
            label="En cours",
            value=status_map.get(ShipmentStatus.PICKING, 0),
            help_text="Expéditions non totalement étiquetées.",
            url=reverse("scan:scan_shipments_ready"),
        ),
        _build_card(
            label="Prêtes",
            value=status_map.get(ShipmentStatus.PACKED, 0),
            help_text="Toutes étiquetées, prêtes au planning.",
            url=reverse("scan:scan_shipments_ready"),
            tone="success",
        ),
        _build_card(
            label="Planifiées (semaine)",
            value=shipments_with_tracking.filter(
                status=ShipmentStatus.PLANNED,
                planned_at__date__gte=week_start,
                planned_at__date__lt=week_end,
            ).count(),
            help_text="Date du statut Planifié sur semaine courante.",
            url=reverse("scan:scan_shipments_tracking"),
        ),
        _build_card(
            label="En transit",
            value=in_transit_count,
            help_text="Planifié + Expédié + Reçu escale.",
            url=reverse("scan:scan_shipments_tracking"),
        ),
        _build_card(
            label="Litiges ouverts",
            value=shipments_scope.filter(
                is_disputed=True,
                closed_at__isnull=True,
            ).count(),
            help_text="Expéditions bloquées à traiter.",
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
            label="En préparation",
            value=cartons_scope.filter(status=CartonStatus.PICKING).count(),
            help_text="Colis en cours de préparation.",
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label="Prêts non affectés",
            value=cartons_scope.filter(
                status=CartonStatus.PACKED,
                shipment__isnull=True,
            ).count(),
            help_text="Disponibles pour expédition.",
            url=reverse("scan:scan_cartons_ready"),
            tone="warn",
        ),
        _build_card(
            label="Affectés non étiquetés",
            value=assigned_scope.count(),
            help_text="Affectés mais pas encore étiquetés.",
            url=reverse("scan:scan_cartons_ready"),
        ),
        _build_card(
            label="Étiquetés",
            value=labeled_scope.count(),
            help_text="Colis étiquetés prêts au départ.",
            url=reverse("scan:scan_cartons_ready"),
            tone="success",
        ),
        _build_card(
            label="Colis expédiés",
            value=shipped_scope.count(),
            help_text="Sortis après l'étape OK mise à bord.",
            url=reverse("scan:scan_cartons_ready"),
        ),
    ]

    stock_snapshot = _stock_snapshot()
    stock_cards = [
        _build_card(
            label="Produits actifs",
            value=stock_snapshot["active_products_count"],
            help_text="Produits actifs catalogués.",
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label="Lots disponibles",
            value=stock_snapshot["available_lots_count"],
            help_text="Lots avec stock disponible.",
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label="Quantité disponible",
            value=stock_snapshot["total_available_qty"],
            help_text="Somme des quantités disponibles.",
            url=reverse("scan:scan_stock"),
        ),
        _build_card(
            label=f"Stock bas (< {LOW_STOCK_THRESHOLD})",
            value=stock_snapshot["low_stock_count"],
            help_text="Produits sous le seuil global.",
            url=reverse("scan:scan_stock"),
            tone="danger",
        ),
    ]

    flow_cards = [
        _build_card(
            label="Réceptions en attente",
            value=Receipt.objects.filter(status=ReceiptStatus.DRAFT).count(),
            help_text="Réceptions non finalisées.",
            url=reverse("scan:scan_receipts_view"),
            tone="warn",
        ),
        _build_card(
            label="Cmd en attente de validation",
            value=Order.objects.filter(
                review_status=OrderReviewStatus.PENDING
            ).count(),
            help_text="Demandes à valider.",
            url=reverse("scan:scan_orders_view"),
        ),
        _build_card(
            label="Cmd à modifier",
            value=Order.objects.filter(
                review_status=OrderReviewStatus.CHANGES_REQUESTED
            ).count(),
            help_text="Retours en correction.",
            url=reverse("scan:scan_orders_view"),
            tone="warn",
        ),
        _build_card(
            label="Cmd validées sans expédition",
            value=Order.objects.filter(
                review_status=OrderReviewStatus.APPROVED,
                shipment__isnull=True,
            ).count(),
            help_text="Validées, en attente de création d'expédition.",
            url=reverse("scan:scan_orders_view"),
        ),
    ]

    tracking_cards = [
        _build_card(
            label="Planifiées sans mise à bord >72h",
            value=planned_alert_count,
            help_text=f"Sans étape OK mise à bord depuis {TRACKING_ALERT_HOURS}h.",
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if planned_alert_count else "success",
        ),
        _build_card(
            label="Expédiées sans reçu escale >72h",
            value=shipped_alert_count,
            help_text=f"Sans confirmation correspondant depuis {TRACKING_ALERT_HOURS}h.",
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if shipped_alert_count else "success",
        ),
        _build_card(
            label="Reçu escale sans livraison >72h",
            value=correspondent_alert_count,
            help_text=f"Sans confirmation destinataire depuis {TRACKING_ALERT_HOURS}h.",
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if correspondent_alert_count else "success",
        ),
        _build_card(
            label="Dossiers clôturables",
            value=closable_count,
            help_text="Toutes étapes complétées, dossier clos possible.",
            url=reverse("scan:scan_shipments_tracking"),
            tone="success" if closable_count else "neutral",
        ),
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
        "activity_cards": activity_cards,
        "shipment_cards": shipment_cards,
        "carton_cards": carton_cards,
        "stock_cards": stock_cards,
        "flow_cards": flow_cards,
        "tracking_cards": tracking_cards,
        "low_stock_rows": stock_snapshot["low_stock_rows"],
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
        "tracking_alert_hours": TRACKING_ALERT_HOURS,
        "shipment_chart_rows": chart_rows,
        "shipments_total": shipments_total,
    }
    return render(request, TEMPLATE_DASHBOARD, context)
