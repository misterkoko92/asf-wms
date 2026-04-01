from django.conf import settings as django_settings
from django.db import models
from django.db.models import F
from django.utils import timezone

from ..design_tokens import PRIORITY_ONE_TOKEN_DEFAULTS


class WmsChange(models.Model):
    version = models.PositiveBigIntegerField(default=1)
    last_changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"WMS change v{self.version}"

    @classmethod
    def bump(cls) -> None:
        now = timezone.now()
        updated = cls.objects.filter(pk=1).update(
            version=F("version") + 1,
            last_changed_at=now,
        )
        if not updated:
            cls.objects.create(pk=1, version=1, last_changed_at=now)

    @classmethod
    def get_state(cls):
        now = timezone.now()
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"version": 1, "last_changed_at": now},
        )
        return obj


class IntegrationDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class IntegrationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class IntegrationEvent(models.Model):
    direction = models.CharField(
        max_length=20,
        choices=IntegrationDirection.choices,
        default=IntegrationDirection.INBOUND,
    )
    source = models.CharField(max_length=80)
    target = models.CharField(max_length=80, blank=True)
    event_type = models.CharField(max_length=120)
    external_id = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=IntegrationStatus.choices,
        default=IntegrationStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["direction", "status", "created_at"]),
            models.Index(fields=["source", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.event_type} ({self.direction})"


class WorkflowBlockageClaim(models.Model):
    blockage_key = models.CharField(max_length=160, unique=True)
    category = models.CharField(max_length=32)
    label = models.CharField(max_length=120, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    owner = models.CharField(max_length=20, blank=True)
    claimed_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_blockage_claims",
    )
    claimed_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-claimed_at", "-id"]
        indexes = [
            models.Index(
                fields=["category", "claimed_at"],
                name="wms_workflo_categor_25334f_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.blockage_key


class ShipmentWorkflowProjection(models.Model):
    shipment = models.OneToOneField(
        "wms.Shipment",
        on_delete=models.CASCADE,
        related_name="workflow_projection",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipment_workflow_projections",
    )
    reference = models.CharField(max_length=80, blank=True, default="")
    tracking_token = models.UUIDField(null=True, blank=True)
    destination_label = models.CharField(max_length=200, blank=True, default="")
    shipment_status = models.CharField(max_length=40, blank=True, default="")
    shipment_created_at = models.DateTimeField(null=True, blank=True)
    planned_at = models.DateTimeField(null=True, blank=True)
    boarding_ok_at = models.DateTimeField(null=True, blank=True)
    received_correspondent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    current_segment = models.CharField(max_length=40, blank=True, default="")
    segment_started_at = models.DateTimeField(null=True, blank=True)
    segment_age_hours = models.FloatField(default=0.0)
    is_closed = models.BooleanField(default=False)
    lead_hours_planned_to_boarding = models.FloatField(null=True, blank=True)
    lead_hours_boarding_to_correspondent = models.FloatField(null=True, blank=True)
    lead_hours_correspondent_to_delivery = models.FloatField(null=True, blank=True)
    lead_hours_delivery_to_close = models.FloatField(null=True, blank=True)
    lead_hours_total_to_delivery = models.FloatField(null=True, blank=True)
    has_open_dispute = models.BooleanField(default=False)
    dispute_reason = models.CharField(max_length=40, blank=True, default="")
    dispute_owner = models.CharField(max_length=20, blank=True, default="")
    dispute_opened_at = models.DateTimeField(null=True, blank=True)
    dispute_resolved_at = models.DateTimeField(null=True, blank=True)
    dispute_resolution_hours = models.FloatField(null=True, blank=True)
    delay_state = models.CharField(max_length=20, blank=True, default="on_time")
    current_delay_hours = models.FloatField(default=0.0)
    active_blockage_category = models.CharField(max_length=32, blank=True, default="")
    projected_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["reference", "shipment_id"]
        indexes = [
            models.Index(
                fields=["shipment_status", "current_segment"],
                name="wms_shipwf_status_seg_idx",
            ),
            models.Index(
                fields=["delay_state", "is_closed"],
                name="wms_shipwf_delay_closed_idx",
            ),
            models.Index(
                fields=["has_open_dispute", "projected_at"],
                name="wms_shipwf_dispute_proj_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.reference or f"workflow-projection:{self.shipment_id}"


class OpsPilotageSnapshot(models.Model):
    snapshot_date = models.DateField()
    scope_type = models.CharField(max_length=40)
    scope_key = models.CharField(max_length=120)
    metric_key = models.CharField(max_length=80)
    metric_value = models.FloatField(default=0.0)
    payload = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = [
            "-snapshot_date",
            "scope_type",
            "scope_key",
            "metric_key",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot_date", "scope_type", "scope_key", "metric_key"],
                name="wms_ops_snapshot_unique_metric",
            )
        ]
        indexes = [
            models.Index(
                fields=["snapshot_date", "scope_type"],
                name="wms_ops_snap_date_scope_idx",
            ),
            models.Index(
                fields=["scope_type", "metric_key"],
                name="wms_ops_snap_scope_metric_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.snapshot_date}:{self.scope_type}:{self.scope_key}:{self.metric_key}"


class OpsEscalation(models.Model):
    escalation_key = models.CharField(max_length=160, unique=True)
    category = models.CharField(max_length=40)
    scope_type = models.CharField(max_length=40)
    scope_key = models.CharField(max_length=120)
    severity = models.CharField(max_length=20)
    owner = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=20, default="open")
    first_detected_at = models.DateTimeField(default=timezone.now)
    last_detected_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["status", "-last_detected_at", "category", "escalation_key"]
        indexes = [
            models.Index(fields=["status", "category"], name="wms_ops_esc_status_cat_idx"),
            models.Index(fields=["scope_type", "scope_key"], name="wms_ops_esc_scope_idx"),
        ]

    def __str__(self) -> str:
        return self.escalation_key


class PlanningCommunicationArtifact(models.Model):
    planning_version = models.ForeignKey(
        "wms.PlanningVersion",
        on_delete=models.CASCADE,
        related_name="communication_artifacts",
    )
    output_type = models.CharField(max_length=40)
    status = models.CharField(max_length=20)
    backend = models.CharField(max_length=40, blank=True, default="")
    file_name = models.CharField(max_length=255, blank=True, default="")
    generated_at = models.DateTimeField(default=timezone.now)
    error_message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["planning_version_id", "output_type", "-generated_at", "-id"]
        indexes = [
            models.Index(
                fields=["planning_version", "output_type", "-generated_at"],
                name="wms_plan_comm_lookup_idx",
            ),
            models.Index(
                fields=["output_type", "status"],
                name="wms_plan_comm_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.planning_version_id}:{self.output_type}:{self.status}"


def _safe_int(value, *, default, minimum):
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, resolved)


class WmsRuntimeSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    low_stock_threshold = models.PositiveIntegerField(default=20)
    tracking_alert_hours = models.PositiveIntegerField(default=72)
    workflow_blockage_hours = models.PositiveIntegerField(default=72)
    stale_drafts_age_days = models.PositiveIntegerField(default=30)
    pilotage_dispute_unassigned_hours = models.PositiveIntegerField(default=12)
    pilotage_workflow_blockage_unclaimed_hours = models.PositiveIntegerField(default=12)
    pilotage_queue_backlog_threshold = models.PositiveIntegerField(default=3)
    pilotage_planning_tension_pct = models.PositiveIntegerField(default=80)
    pilotage_planning_critical_pct = models.PositiveIntegerField(default=95)
    email_queue_max_attempts = models.PositiveIntegerField(default=5)
    email_queue_retry_base_seconds = models.PositiveIntegerField(default=60)
    email_queue_retry_max_seconds = models.PositiveIntegerField(default=3600)
    email_queue_processing_timeout_seconds = models.PositiveIntegerField(default=900)
    enable_shipment_track_legacy = models.BooleanField(default=True)
    design_font_heading = models.CharField(
        max_length=160,
        default='"DM Sans", "Aptos", "Segoe UI", sans-serif',
    )
    design_font_h1 = models.CharField(
        max_length=120,
        default="DM Sans",
    )
    design_font_h2 = models.CharField(
        max_length=120,
        default="DM Sans",
    )
    design_font_h3 = models.CharField(
        max_length=120,
        default="DM Sans",
    )
    design_font_body = models.CharField(
        max_length=160,
        default='"Nunito Sans", "Aptos", "Segoe UI", sans-serif',
    )
    design_color_primary = models.CharField(max_length=16, default="#6f9a8d")
    design_color_secondary = models.CharField(max_length=16, default="#e7c3a8")
    design_color_background = models.CharField(max_length=16, default="#f6f8f5")
    design_color_surface = models.CharField(max_length=16, default="#fffdf9")
    design_color_border = models.CharField(max_length=16, default="#d9e2dc")
    design_color_text = models.CharField(max_length=16, default="#2f3a36")
    design_color_text_soft = models.CharField(max_length=16, default="#5a6964")
    design_tokens = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wms_runtime_settings_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres runtime WMS"
        verbose_name_plural = "Paramètres runtime WMS"

    def __str__(self) -> str:
        return "Paramètres runtime WMS"

    @classmethod
    def _defaults_from_settings(cls):
        return {
            "low_stock_threshold": 20,
            "tracking_alert_hours": 72,
            "workflow_blockage_hours": 72,
            "stale_drafts_age_days": 30,
            "pilotage_dispute_unassigned_hours": 12,
            "pilotage_workflow_blockage_unclaimed_hours": 12,
            "pilotage_queue_backlog_threshold": 3,
            "pilotage_planning_tension_pct": 80,
            "pilotage_planning_critical_pct": 95,
            "email_queue_max_attempts": _safe_int(
                getattr(django_settings, "EMAIL_QUEUE_MAX_ATTEMPTS", 5),
                default=5,
                minimum=1,
            ),
            "email_queue_retry_base_seconds": _safe_int(
                getattr(django_settings, "EMAIL_QUEUE_RETRY_BASE_SECONDS", 60),
                default=60,
                minimum=1,
            ),
            "email_queue_retry_max_seconds": _safe_int(
                getattr(django_settings, "EMAIL_QUEUE_RETRY_MAX_SECONDS", 3600),
                default=3600,
                minimum=1,
            ),
            "email_queue_processing_timeout_seconds": _safe_int(
                getattr(django_settings, "EMAIL_QUEUE_PROCESSING_TIMEOUT_SECONDS", 900),
                default=900,
                minimum=1,
            ),
            "enable_shipment_track_legacy": bool(
                getattr(django_settings, "ENABLE_SHIPMENT_TRACK_LEGACY", True)
            ),
            "design_font_heading": "DM Sans",
            "design_font_h1": "DM Sans",
            "design_font_h2": "DM Sans",
            "design_font_h3": "DM Sans",
            "design_font_body": "Nunito Sans",
            "design_color_primary": "#6f9a8d",
            "design_color_secondary": "#e7c3a8",
            "design_color_background": "#f6f8f5",
            "design_color_surface": "#fffdf9",
            "design_color_border": "#d9e2dc",
            "design_color_text": "#2f3a36",
            "design_color_text_soft": "#5a6964",
            "design_tokens": dict(PRIORITY_ONE_TOKEN_DEFAULTS),
        }

    @classmethod
    def get_solo(cls):
        obj, _created = cls.objects.get_or_create(
            pk=1,
            defaults=cls._defaults_from_settings(),
        )
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        if self.email_queue_retry_max_seconds < self.email_queue_retry_base_seconds:
            self.email_queue_retry_max_seconds = self.email_queue_retry_base_seconds
        super().save(*args, **kwargs)


class WmsRuntimeSettingsAudit(models.Model):
    settings = models.ForeignKey(
        WmsRuntimeSettings,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wms_runtime_settings_audit_logs",
    )
    change_note = models.CharField(max_length=255, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    previous_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name = "Historique parametres runtime WMS"
        verbose_name_plural = "Historique parametres runtime WMS"

    def __str__(self) -> str:
        return f"Audit runtime {self.changed_at:%Y-%m-%d %H:%M:%S}"
