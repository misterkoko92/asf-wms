from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .document_scan_queue import DOCUMENT_SCAN_QUEUE_EVENT_TYPE, DOCUMENT_SCAN_QUEUE_SOURCE
from .models import (
    IntegrationDirection,
    IntegrationEvent,
    IntegrationStatus,
    Order,
    OrderReviewStatus,
    ShipmentStatus,
    WorkflowBlockageClaim,
)
from .scan_dashboard_sla import build_sla_alert_rows

EMAIL_QUEUE_SOURCE = "wms.email"
EMAIL_QUEUE_EVENT_TYPE = "send_email"

WORKFLOW_BLOCKAGE_CATEGORIES = (
    "creation_expedition",
    "commande",
    "suivi",
    "cloture",
    "queue",
)
WORKFLOW_BLOCKAGE_PRIORITIES = ("high", "medium", "low")
WORKFLOW_BLOCKAGE_CLAIM_OPEN = "open"
WORKFLOW_BLOCKAGE_CLAIM_CLAIMED = "claimed"

_CATEGORY_RANK = {category: index for index, category in enumerate(WORKFLOW_BLOCKAGE_CATEGORIES)}
_PRIORITY_RANK = {priority: index for index, priority in enumerate(WORKFLOW_BLOCKAGE_PRIORITIES)}


def _age_hours(started_at):
    if started_at is None:
        return 0.0
    delta = timezone.now() - started_at
    return max(round(delta.total_seconds() / 3600, 1), 0.0)


def _build_row(
    *,
    blockage_key,
    category,
    kind,
    label,
    reference,
    owner,
    priority,
    started_at,
    url,
):
    if category not in WORKFLOW_BLOCKAGE_CATEGORIES:
        raise ValueError(f"Unsupported workflow blockage category: {category}")
    if priority not in WORKFLOW_BLOCKAGE_PRIORITIES:
        raise ValueError(f"Unsupported workflow blockage priority: {priority}")
    return {
        "blockage_key": blockage_key,
        "category": category,
        "kind": kind,
        "label": label,
        "reference": reference,
        "owner": owner,
        "priority": priority,
        "started_at": started_at,
        "age_hours": _age_hours(started_at),
        "url": url,
        "is_claimed": False,
        "claimed_by": "",
        "claimed_at": None,
        "claim_state": WORKFLOW_BLOCKAGE_CLAIM_OPEN,
    }


def _queue_issue_queryset(*, source, event_type, status=None, stale_before=None):
    queryset = IntegrationEvent.objects.filter(
        direction=IntegrationDirection.OUTBOUND,
        source=source,
        event_type=event_type,
    )
    if status is not None:
        queryset = queryset.filter(status=status)
    if stale_before is not None:
        queryset = queryset.filter(
            status=IntegrationStatus.PROCESSING,
            processed_at__lte=stale_before,
        )
    return queryset.order_by("processed_at", "created_at")


def _merge_claims(rows):
    if not rows:
        return rows
    claims = {
        claim.blockage_key: claim
        for claim in WorkflowBlockageClaim.objects.select_related("claimed_by").filter(
            blockage_key__in=[row["blockage_key"] for row in rows]
        )
    }
    for row in rows:
        claim = claims.get(row["blockage_key"])
        if claim is None:
            continue
        row["is_claimed"] = True
        row["claimed_by"] = claim.claimed_by.get_username() if claim.claimed_by else ""
        row["claimed_at"] = claim.claimed_at
        row["claim_state"] = WORKFLOW_BLOCKAGE_CLAIM_CLAIMED
    rows.sort(
        key=lambda row: (
            1 if row["is_claimed"] else 0,
            _PRIORITY_RANK.get(row["priority"], 99),
            -row["age_hours"],
            _CATEGORY_RANK.get(row["category"], 99),
            row["reference"],
            row["blockage_key"],
        )
    )
    return rows


def build_workflow_blockage_rows(
    *,
    shipments_scope,
    shipments_with_tracking,
    workflow_blockage_hours,
    tracking_alert_hours,
    email_queue_processing_timeout_seconds,
    document_scan_processing_timeout_seconds,
):
    rows = []
    cutoff = timezone.now() - timedelta(hours=workflow_blockage_hours)

    stale_shipments = shipments_scope.filter(
        status__in=[ShipmentStatus.DRAFT, ShipmentStatus.PICKING],
        created_at__lt=cutoff,
        closed_at__isnull=True,
    ).order_by("created_at")
    for shipment in stale_shipments.values("id", "reference", "status", "created_at"):
        rows.append(
            _build_row(
                blockage_key=f"creation_expedition:shipment:{shipment['id']}",
                category="creation_expedition",
                kind="shipment_creation",
                label="Debloquer creation expedition",
                reference=shipment["reference"] or f"EXP-{shipment['id']}",
                owner="magasin",
                priority="high" if shipment["status"] == ShipmentStatus.PICKING else "medium",
                started_at=shipment["created_at"],
                url=reverse("scan:scan_shipment_edit", args=[shipment["id"]]),
            )
        )

    unplanned_orders = Order.objects.filter(
        review_status=OrderReviewStatus.APPROVED,
        shipment__isnull=True,
        created_at__lt=cutoff,
    ).order_by("created_at")
    for order in unplanned_orders.values("id", "reference", "created_at"):
        rows.append(
            _build_row(
                blockage_key=f"commande:order:{order['id']}",
                category="commande",
                kind="order_without_shipment",
                label="Creer expedition",
                reference=order["reference"] or f"CMD-{order['id']}",
                owner="admin",
                priority="high",
                started_at=order["created_at"],
                url=reverse("scan:scan_orders_view"),
            )
        )

    open_disputes = shipments_with_tracking.filter(
        is_disputed=True,
        closed_at__isnull=True,
    ).order_by("dispute_opened_at", "disputed_at", "created_at")
    for shipment in open_disputes.values(
        "id",
        "reference",
        "tracking_token",
        "created_at",
        "disputed_at",
        "dispute_opened_at",
        "dispute_owner",
    ):
        started_at = (
            shipment["dispute_opened_at"] or shipment["disputed_at"] or shipment["created_at"]
        )
        rows.append(
            _build_row(
                blockage_key=f"suivi:shipment_dispute:{shipment['id']}",
                category="suivi",
                kind="shipment_dispute",
                label="Resoudre litige",
                reference=shipment["reference"] or f"EXP-{shipment['id']}",
                owner=shipment["dispute_owner"] or "qualite",
                priority="high",
                started_at=started_at,
                url=reverse("scan:scan_shipment_track", args=[shipment["tracking_token"]]),
            )
        )

    for row in build_sla_alert_rows(
        shipments_with_tracking,
        tracking_alert_hours=tracking_alert_hours,
    ):
        if row["freshness"] != "persistent":
            continue
        rows.append(
            _build_row(
                blockage_key=f"suivi:sla:{row['segment_key']}:{row['shipment_id']}",
                category="suivi",
                kind="shipment_sla_alert",
                label="Traiter retard de suivi",
                reference=row["reference"],
                owner=row["owner"],
                priority=row["priority"],
                started_at=row["started_at"],
                url=reverse("scan:scan_shipment_track", args=[row["tracking_token"]]),
            )
        )

    closable_shipments = shipments_with_tracking.filter(
        status=ShipmentStatus.DELIVERED,
        closed_at__isnull=True,
        is_disputed=False,
        received_recipient_at__isnull=False,
    ).order_by("received_recipient_at", "created_at")
    for shipment in closable_shipments.values(
        "id",
        "reference",
        "tracking_token",
        "received_recipient_at",
    ):
        rows.append(
            _build_row(
                blockage_key=f"cloture:shipment:{shipment['id']}",
                category="cloture",
                kind="shipment_closure",
                label="Clore dossier livre",
                reference=shipment["reference"] or f"EXP-{shipment['id']}",
                owner="qualite",
                priority="medium",
                started_at=shipment["received_recipient_at"],
                url=reverse("scan:scan_shipment_track", args=[shipment["tracking_token"]]),
            )
        )

    email_stale_before = timezone.now() - timedelta(seconds=email_queue_processing_timeout_seconds)
    email_failed_event = _queue_issue_queryset(
        source=EMAIL_QUEUE_SOURCE,
        event_type=EMAIL_QUEUE_EVENT_TYPE,
        status=IntegrationStatus.FAILED,
    ).first()
    if email_failed_event is not None:
        rows.append(
            _build_row(
                blockage_key="queue:email:failed",
                category="queue",
                kind="email_queue_failed",
                label="Investiguer queue email en echec",
                reference=EMAIL_QUEUE_SOURCE,
                owner="admin",
                priority="medium",
                started_at=email_failed_event.created_at,
                url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-health",
            )
        )
    email_stale_event = _queue_issue_queryset(
        source=EMAIL_QUEUE_SOURCE,
        event_type=EMAIL_QUEUE_EVENT_TYPE,
        stale_before=email_stale_before,
    ).first()
    if email_stale_event is not None:
        rows.append(
            _build_row(
                blockage_key="queue:email:stale_processing",
                category="queue",
                kind="email_queue_stale",
                label="Debloquer queue email",
                reference=EMAIL_QUEUE_SOURCE,
                owner="admin",
                priority="high",
                started_at=email_stale_event.processed_at or email_stale_event.created_at,
                url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-health",
            )
        )

    scan_stale_before = timezone.now() - timedelta(seconds=document_scan_processing_timeout_seconds)
    scan_failed_event = _queue_issue_queryset(
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
        status=IntegrationStatus.FAILED,
    ).first()
    if scan_failed_event is not None:
        rows.append(
            _build_row(
                blockage_key="queue:document_scan:failed",
                category="queue",
                kind="document_scan_failed",
                label="Investiguer queue scan doc en echec",
                reference=DOCUMENT_SCAN_QUEUE_SOURCE,
                owner="qualite",
                priority="medium",
                started_at=scan_failed_event.created_at,
                url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-health",
            )
        )
    scan_stale_event = _queue_issue_queryset(
        source=DOCUMENT_SCAN_QUEUE_SOURCE,
        event_type=DOCUMENT_SCAN_QUEUE_EVENT_TYPE,
        stale_before=scan_stale_before,
    ).first()
    if scan_stale_event is not None:
        rows.append(
            _build_row(
                blockage_key="queue:document_scan:stale_processing",
                category="queue",
                kind="document_scan_stale",
                label="Debloquer queue scan doc",
                reference=DOCUMENT_SCAN_QUEUE_SOURCE,
                owner="qualite",
                priority="high",
                started_at=scan_stale_event.processed_at or scan_stale_event.created_at,
                url=f"{reverse('scan:scan_dashboard')}#scan-dashboard-health",
            )
        )

    return _merge_claims(rows)


def summarize_workflow_blockage_rows(rows):
    return {
        "open_count": len(rows),
        "claimed_count": sum(1 for row in rows if row["is_claimed"]),
        "unclaimed_count": sum(1 for row in rows if not row["is_claimed"]),
    }


def claim_workflow_blockage(*, row, user):
    claim, _created = WorkflowBlockageClaim.objects.update_or_create(
        blockage_key=row["blockage_key"],
        defaults={
            "category": row["category"],
            "label": row["label"],
            "reference": row["reference"],
            "owner": row["owner"],
            "claimed_by": user if getattr(user, "is_authenticated", False) else None,
            "claimed_at": timezone.now(),
        },
    )
    return claim


def release_workflow_blockage(*, blockage_key):
    WorkflowBlockageClaim.objects.filter(blockage_key=blockage_key).delete()


def workflow_blockage_row_by_key(rows, blockage_key):
    for row in rows:
        if row["blockage_key"] == blockage_key:
            return row
    return None
