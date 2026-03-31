from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, F, IntegerField, Q, Sum, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.views.decorators.http import require_http_methods

from .document_scan_queue import (
    DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
    DOCUMENT_SCAN_QUEUE_SOURCE,
)
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
    ShipmentWorkflowProjection,
)
from .runtime_settings import get_runtime_config
from .scan_dashboard_destination_risk import build_destination_risk_snapshot
from .scan_dashboard_sla import (
    annotate_shipment_tracking_dates,
    build_sla_alert_rows,
    build_sla_rows,
    summarize_sla_alert_rows,
)
from .scan_permissions import user_is_preparateur
from .view_permissions import scan_staff_required
from .workflow_blockage_queue import (
    WORKFLOW_BLOCKAGE_CLAIM_CLAIMED,
    build_workflow_blockage_rows,
    claim_workflow_blockage,
    release_workflow_blockage,
    summarize_workflow_blockage_rows,
    workflow_blockage_row_by_key,
)

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
ACTION_QUEUE_OWNERS = ("magasin", "qualite", "admin", "portal")
ACTION_QUEUE_PRIORITIES = ("high", "medium", "low")

SHIPMENT_STATUS_ORDER = (
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
)
SLA_SEGMENT_LABELS = {
    "planned_to_boarding": _("Planifié -> OK mise à bord"),
    "boarding_to_correspondent": _("OK mise à bord -> Reçu escale"),
    "correspondent_to_delivery": _("Reçu escale -> Livré"),
    "planned_to_delivery": _("Planifié -> Livré"),
}
SLA_ALERT_ACTION_LABELS = {
    "planned_to_boarding": _("Relancer mise à bord"),
    "boarding_to_correspondent": _("Relancer reçu escale"),
    "correspondent_to_delivery": _("Relancer livraison"),
}
SLA_ALERT_FRESHNESS_LABELS = {
    "new": _("Nouveau retard"),
    "persistent": _("Retard persistant"),
}
SLA_ALERT_SEVERITY_LABELS = {
    "high": _("Élevée"),
    "critical": _("Critique"),
}
WORKFLOW_BLOCKAGE_CATEGORY_LABELS = {
    "creation_expedition": _("Création expédition"),
    "commande": _("Commande"),
    "suivi": _("Suivi"),
    "cloture": _("Clôture"),
    "queue": _("Queue"),
}
WORKFLOW_BLOCKAGE_KIND_LABELS = {
    "shipment_creation": _("Débloquer création expédition"),
    "order_without_shipment": _("Créer expédition"),
    "shipment_dispute": _("Résoudre litige"),
    "shipment_sla_alert": _("Traiter retard de suivi"),
    "shipment_closure": _("Clore dossier livré"),
    "email_queue_failed": _("Investiguer queue email en échec"),
    "email_queue_stale": _("Débloquer queue email"),
    "document_scan_failed": _("Investiguer queue scan doc en échec"),
    "document_scan_stale": _("Débloquer queue scan doc"),
}
WORKFLOW_BLOCKAGE_CLAIM_STATE_LABELS = {
    "open": _("À prendre"),
    WORKFLOW_BLOCKAGE_CLAIM_CLAIMED: _("Pris en charge"),
}


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


def _extend_card(card, **updates):
    value = dict(card)
    value.update(updates)
    return value


def _build_dashboard_section(*, section_id, title, cards, description=""):
    return {
        "id": section_id,
        "title": title,
        "description": description,
        "cards": cards,
    }


def _positive_int(value, *, default):
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, int_value)


def _age_hours(started_at):
    if started_at is None:
        return 0.0
    delta = timezone.now() - started_at
    return max(round(delta.total_seconds() / 3600, 1), 0.0)


def _build_action_queue_row(
    *,
    label,
    reference,
    owner,
    priority,
    url,
    started_at=None,
    cta_label=None,
):
    if owner not in ACTION_QUEUE_OWNERS:
        raise ValueError(f"Unsupported action queue owner: {owner}")
    if priority not in ACTION_QUEUE_PRIORITIES:
        raise ValueError(f"Unsupported action queue priority: {priority}")
    return {
        "label": label,
        "reference": reference,
        "owner": owner,
        "priority": priority,
        "url": url,
        "age_hours": _age_hours(started_at),
        "cta_label": cta_label or _("Voir le détail"),
    }


def _status_count_map(shipments_qs):
    status_counts = {
        item["status"]: item["total"]
        for item in shipments_qs.values("status").annotate(total=Count("id"))
    }
    return {status: status_counts.get(status, 0) for status in SHIPMENT_STATUS_ORDER}


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


def _document_scan_timeout_seconds():
    return _positive_int(
        getattr(
            settings,
            "DOCUMENT_SCAN_QUEUE_PROCESSING_TIMEOUT_SECONDS",
            DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
        ),
        default=DOCUMENT_SCAN_DEFAULT_PROCESSING_TIMEOUT_SECONDS,
    )


def _document_scan_queue_snapshot(*, processing_timeout_seconds):
    queue_qs = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
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


@scan_staff_required
@require_http_methods(["GET", "POST"])
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

    destinations = Destination.objects.filter(is_active=True).order_by("city")
    destination_raw = (request.GET.get("destination") or "").strip()
    selected_destination = None
    if destination_raw:
        selected_destination = destinations.filter(pk=destination_raw).first()

    shipments_scope = Shipment.objects.filter(archived_at__isnull=True)
    if selected_destination:
        shipments_scope = shipments_scope.filter(destination=selected_destination)

    shipments_with_tracking = annotate_shipment_tracking_dates(shipments_scope)
    document_scan_timeout_seconds = _document_scan_timeout_seconds()
    workflow_blockage_base_rows = build_workflow_blockage_rows(
        shipments_scope=shipments_scope,
        shipments_with_tracking=shipments_with_tracking,
        workflow_blockage_hours=workflow_blockage_hours,
        tracking_alert_hours=tracking_alert_hours,
        email_queue_processing_timeout_seconds=queue_processing_timeout_seconds,
        document_scan_processing_timeout_seconds=document_scan_timeout_seconds,
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        blockage_key = (request.POST.get("blockage_key") or "").strip()
        blockage_row = workflow_blockage_row_by_key(workflow_blockage_base_rows, blockage_key)
        if action == "claim_workflow_blockage":
            if blockage_row is None:
                messages.error(request, _("Blocage introuvable ou déjà résolu."))
            else:
                claim_workflow_blockage(row=blockage_row, user=request.user)
                messages.success(request, _("Blocage pris en charge."))
        elif action == "release_workflow_blockage":
            release_workflow_blockage(blockage_key=blockage_key)
            messages.success(request, _("Prise en charge libérée."))
        else:
            messages.error(request, _("Action dashboard inconnue."))
        return redirect(request.get_full_path())
    status_map = _status_count_map(shipments_scope)

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
    document_scan_snapshot = _document_scan_queue_snapshot(
        processing_timeout_seconds=document_scan_timeout_seconds
    )
    document_scan_cards = [
        _build_card(
            label=_("Queue scan doc en attente"),
            value=document_scan_snapshot["pending_count"],
            help_text=_("Scans document en file d'attente."),
            url=reverse("scan:scan_dashboard"),
            tone="warn" if document_scan_snapshot["pending_count"] else "success",
        ),
        _build_card(
            label=_("Queue scan doc en traitement"),
            value=document_scan_snapshot["processing_count"],
            help_text=_("Scans document claimés en cours."),
            url=reverse("scan:scan_dashboard"),
        ),
        _build_card(
            label=_("Queue scan doc en échec"),
            value=document_scan_snapshot["failed_count"],
            help_text=_("Scans document à investiguer ou rejouer."),
            url=reverse("scan:scan_dashboard"),
            tone="danger" if document_scan_snapshot["failed_count"] else "success",
        ),
        _build_card(
            label=_("Queue scan doc bloquée (timeout)"),
            value=document_scan_snapshot["stale_processing_count"],
            help_text=(
                _("Scans document processing au-delà du timeout (%(seconds)ss).")
                % {"seconds": document_scan_timeout_seconds}
            ),
            url=reverse("scan:scan_dashboard"),
            tone="danger" if document_scan_snapshot["stale_processing_count"] else "success",
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
    workflow_blockage_summary = summarize_workflow_blockage_rows(workflow_blockage_base_rows)
    workflow_blockage_summary_cards = [
        _build_card(
            label=_("Blocages ouverts"),
            value=workflow_blockage_summary["open_count"],
            help_text=_("Total des blocages visibles dans la file."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-workflow-blockages",
            tone="danger" if workflow_blockage_summary["open_count"] else "success",
        ),
        _build_card(
            label=_("Sans prise en charge"),
            value=workflow_blockage_summary["unclaimed_count"],
            help_text=_("Blocages encore sans opérateur."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-workflow-blockages",
            tone="danger" if workflow_blockage_summary["unclaimed_count"] else "success",
        ),
        _build_card(
            label=_("Pris en charge"),
            value=workflow_blockage_summary["claimed_count"],
            help_text=_("Blocages déjà pris par un opérateur."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-workflow-blockages",
            tone="warn" if workflow_blockage_summary["claimed_count"] else "neutral",
        ),
    ]
    workflow_blockage_rows = [
        {
            **row,
            "category_label": WORKFLOW_BLOCKAGE_CATEGORY_LABELS[row["category"]],
            "label": WORKFLOW_BLOCKAGE_KIND_LABELS.get(row["kind"], row["label"]),
            "claim_state_label": WORKFLOW_BLOCKAGE_CLAIM_STATE_LABELS[row["claim_state"]],
            "cta_label": _("Ouvrir"),
        }
        for row in workflow_blockage_base_rows
    ]
    destination_projection_scope = ShipmentWorkflowProjection.objects.select_related(
        "destination"
    ).all()
    if selected_destination:
        destination_projection_scope = destination_projection_scope.filter(
            destination=selected_destination
        )
    destination_risk_snapshot = build_destination_risk_snapshot(
        destination_projection_scope,
        limit=5,
    )
    destination_risk_summary = destination_risk_snapshot["summary"]
    destination_risk_summary_cards = [
        _build_card(
            label=_("Destinations critiques"),
            value=destination_risk_summary["critical_destinations_count"],
            help_text=_("Destinations avec au moins une expédition critique."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-destination-risk",
            tone=(
                "danger" if destination_risk_summary["critical_destinations_count"] else "success"
            ),
        ),
        _build_card(
            label=_("Destinations avec litiges"),
            value=destination_risk_summary["disputed_destinations_count"],
            help_text=_("Destinations avec au moins un dossier en litige."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-destination-risk",
            tone=(
                "danger" if destination_risk_summary["disputed_destinations_count"] else "success"
            ),
        ),
        _build_card(
            label=_("Plus ancien dossier ouvert"),
            value=f"{destination_risk_summary['oldest_open_segment_age_hours']:.1f}h",
            help_text=_("Ancienneté maximale des dossiers encore ouverts."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-destination-risk",
            tone=(
                "warn" if destination_risk_summary["oldest_open_segment_age_hours"] else "success"
            ),
        ),
    ]
    destination_risk_rows = destination_risk_snapshot["rows"]

    sla_rows = build_sla_rows(
        shipments_with_tracking.filter(status__in=list(SHIPMENT_STATUS_ORDER)[3:]),
        tracking_alert_hours=tracking_alert_hours,
    )
    sla_cards = [
        _build_card(
            label=_("%(label)s >%(hours)sh")
            % {
                "label": SLA_SEGMENT_LABELS[row["segment_key"]],
                "hours": row["target_hours"],
            },
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
    sla_alert_base_rows = build_sla_alert_rows(
        shipments_with_tracking,
        tracking_alert_hours=tracking_alert_hours,
    )
    sla_alert_summary = summarize_sla_alert_rows(sla_alert_base_rows)
    sla_alert_summary_cards = [
        _build_card(
            label=_("Nouveaux retards"),
            value=sla_alert_summary["new_count"],
            help_text=_("Retards entre 1x et 2x le seuil de suivi."),
            url=reverse("scan:scan_shipments_tracking"),
            tone="warn" if sla_alert_summary["new_count"] else "success",
        ),
        _build_card(
            label=_("Retards persistants"),
            value=sla_alert_summary["persistent_count"],
            help_text=_("Retards entre 2x et 3x le seuil de suivi."),
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if sla_alert_summary["persistent_count"] else "success",
        ),
        _build_card(
            label=_("Retards critiques"),
            value=sla_alert_summary["critical_count"],
            help_text=_("Retards au-delà de 3x le seuil de suivi."),
            url=reverse("scan:scan_shipments_tracking"),
            tone="danger" if sla_alert_summary["critical_count"] else "success",
        ),
    ]
    sla_alert_rows = [
        {
            "label": SLA_ALERT_ACTION_LABELS[row["segment_key"]],
            "reference": row["reference"],
            "segment": SLA_SEGMENT_LABELS[row["segment_key"]],
            "owner": row["owner"],
            "freshness": row["freshness"],
            "freshness_label": SLA_ALERT_FRESHNESS_LABELS[row["freshness"]],
            "severity": row["severity"],
            "severity_label": SLA_ALERT_SEVERITY_LABELS[row["severity"]],
            "delay_hours": row["delay_hours"],
            "age_hours": row["age_hours"],
            "priority": row["priority"],
            "started_at": row["started_at"],
            "url": reverse("scan:scan_shipment_track", args=[row["tracking_token"]]),
        }
        for row in sla_alert_base_rows
    ]

    page_actions = [
        {
            "label": _("Nouveau colis"),
            "url": reverse("scan:scan_pack"),
            "tone": "tertiary",
        },
        {
            "label": _("Nouvelle expédition"),
            "url": reverse("scan:scan_shipment_create"),
            "tone": "primary",
        },
        {
            "label": _("Suivi expéditions"),
            "url": reverse("scan:scan_shipments_tracking"),
            "tone": "tertiary",
        },
        {
            "label": _("Vue stock"),
            "url": reverse("scan:scan_stock"),
            "tone": "tertiary",
        },
    ]
    dashboard_anchors = [
        {"id": "scan-dashboard-priorities", "label": _("Priorités")},
        {"id": "scan-dashboard-action-queue", "label": _("Actions")},
        {"id": "scan-dashboard-destination-risk", "label": _("Destinations")},
        {"id": "scan-dashboard-pilotage", "label": _("Pilotage")},
        {"id": "scan-dashboard-flow", "label": _("Flux")},
        {"id": "scan-dashboard-health", "label": _("Santé")},
    ]
    action_queue_rows = []
    for row in workflow_blockage_rows:
        if row["is_claimed"]:
            continue
        action_queue_rows.append(
            _build_action_queue_row(
                label=row["label"],
                reference=row["reference"],
                owner=row["owner"],
                priority=row["priority"],
                url=row["url"],
                started_at=row["started_at"],
                cta_label=_("Ouvrir le dossier"),
            )
        )
        if len(action_queue_rows) >= 5:
            break
    for row in stock_snapshot["low_stock_rows"][:3]:
        action_queue_rows.append(
            _build_action_queue_row(
                label=_("Réappro %(name)s") % {"name": row["name"]},
                reference=row["sku"],
                owner="magasin",
                priority="high",
                url=reverse("scan:scan_stock"),
            )
        )
    for order in Order.objects.filter(review_status=OrderReviewStatus.PENDING).order_by(
        "-created_at"
    )[:3]:
        action_queue_rows.append(
            _build_action_queue_row(
                label=_("Valider commande"),
                reference=order.reference or f"CMD-{order.pk}",
                owner="admin",
                priority="medium",
                url=reverse("scan:scan_orders_view"),
                started_at=order.created_at,
            )
        )
    action_queue_rows = action_queue_rows[:10]
    priority_cards = [
        _build_card(
            label=_("Expéditions prêtes"),
            value=status_map.get(ShipmentStatus.PACKED, 0),
            help_text=_("Toutes étiquetées, prêtes au planning."),
            url=reverse("scan:scan_shipments_ready"),
            tone="success",
        ),
        _build_card(
            label=_("Blocages workflow"),
            value=sum(workflow_blockage_snapshot.values()),
            help_text=_("Commandes et dossiers bloqués à traiter."),
            url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-workflow-blockages",
            tone="danger" if sum(workflow_blockage_snapshot.values()) else "success",
        ),
        _build_card(
            label=_("Suivi en retard"),
            value=planned_alert_count + shipped_alert_count + correspondent_alert_count,
            help_text=_("Expéditions en attente d'une étape de suivi."),
            url=reverse("scan:scan_shipments_tracking"),
            tone=(
                "danger"
                if planned_alert_count + shipped_alert_count + correspondent_alert_count
                else "success"
            ),
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
        _build_card(
            label=_("Stock bas"),
            value=stock_snapshot["low_stock_count"],
            help_text=_("Produits sous le seuil global."),
            url=reverse("scan:scan_stock"),
            tone="danger" if stock_snapshot["low_stock_count"] else "success",
        ),
        _build_card(
            label=_("Queue email"),
            value=email_queue_snapshot["failed_count"]
            + email_queue_snapshot["stale_processing_count"],
            help_text=_("Échecs ou traitements bloqués à investiguer."),
            url=reverse("scan:scan_dashboard"),
            tone=(
                "danger"
                if email_queue_snapshot["failed_count"]
                + email_queue_snapshot["stale_processing_count"]
                else "success"
            ),
        ),
    ]
    priority_cards = [
        _extend_card(card, cta_label=cta_label)
        for card, cta_label in zip(
            priority_cards,
            [
                _("Voir les expéditions prêtes"),
                _("Traiter les blocages workflow"),
                _("Ouvrir le suivi expédition"),
                _("Traiter les litiges"),
                _("Contrôler le stock"),
                _("Investiguer la queue email"),
            ],
        )
    ]
    flow_sections = [
        _build_dashboard_section(
            section_id="scan-dashboard-stock",
            title=_("Stock"),
            description=_("Synthèse stock et produits sous seuil."),
            cards=stock_cards,
        ),
        _build_dashboard_section(
            section_id="scan-dashboard-cartons",
            title=_("Colis"),
            description=_("État opérationnel des colis."),
            cards=carton_cards,
        ),
        _build_dashboard_section(
            section_id="scan-dashboard-receipts-orders",
            title=_("Réceptions / Commandes"),
            description=_("Flux entrants et demandes à traiter."),
            cards=flow_cards,
        ),
    ]
    system_health_sections = [
        _build_dashboard_section(
            section_id="scan-dashboard-technical",
            title=_("Technique / Queue email"),
            description=_("État de la file email et du traitement."),
            cards=technical_cards,
        ),
        _build_dashboard_section(
            section_id="scan-dashboard-document-scan",
            title=_("Technique / Scan documentaire"),
            description=_("État de la file antivirus et du traitement."),
            cards=document_scan_cards,
        ),
        _build_dashboard_section(
            section_id="scan-dashboard-sla",
            title=_("Suivi SLA"),
            description=_("Temps de passage entre étapes de suivi."),
            cards=sla_cards,
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
        "kpi_start": kpi_start_date.isoformat(),
        "kpi_end": kpi_end_date.isoformat(),
        "kpi_cards": kpi_cards,
        "activity_cards": activity_cards,
        "shipment_cards": shipment_cards,
        "carton_cards": carton_cards,
        "stock_cards": stock_cards,
        "flow_cards": flow_cards,
        "tracking_cards": tracking_cards,
        "technical_cards": technical_cards,
        "document_scan_cards": document_scan_cards,
        "workflow_blockage_cards": workflow_blockage_cards,
        "workflow_blockage_summary_cards": workflow_blockage_summary_cards,
        "workflow_blockage_rows": workflow_blockage_rows,
        "destination_risk_summary_cards": destination_risk_summary_cards,
        "destination_risk_rows": destination_risk_rows,
        "sla_cards": sla_cards,
        "sla_alert_summary_cards": sla_alert_summary_cards,
        "sla_alert_rows": sla_alert_rows,
        "page_actions": page_actions,
        "dashboard_anchors": dashboard_anchors,
        "action_queue_rows": action_queue_rows,
        "priority_cards": priority_cards,
        "flow_sections": flow_sections,
        "system_health_sections": system_health_sections,
        "low_stock_rows": stock_snapshot["low_stock_rows"],
        "low_stock_threshold": low_stock_threshold,
        "tracking_alert_hours": tracking_alert_hours,
        "workflow_blockage_hours": workflow_blockage_hours,
    }
    return render(request, TEMPLATE_DASHBOARD, context)
