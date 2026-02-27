from django.conf import settings as django_settings
from django.db import models
from django.db.models import F
from django.utils import timezone


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


class UiMode(models.TextChoices):
    LEGACY = "legacy", "Legacy"
    NEXT = "next", "Next"


class UserUiPreference(models.Model):
    user = models.OneToOneField(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wms_ui_preference",
    )
    ui_mode = models.CharField(
        max_length=16,
        choices=UiMode.choices,
        default=UiMode.LEGACY,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id"]
        verbose_name = "Preference interface utilisateur"
        verbose_name_plural = "Preferences interface utilisateur"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.ui_mode}"


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
    email_queue_max_attempts = models.PositiveIntegerField(default=5)
    email_queue_retry_base_seconds = models.PositiveIntegerField(default=60)
    email_queue_retry_max_seconds = models.PositiveIntegerField(default=3600)
    email_queue_processing_timeout_seconds = models.PositiveIntegerField(default=900)
    enable_shipment_track_legacy = models.BooleanField(default=True)
    design_font_heading = models.CharField(
        max_length=160,
        default='"DM Sans", "Aptos", "Segoe UI", sans-serif',
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
            "design_font_heading": '"DM Sans", "Aptos", "Segoe UI", sans-serif',
            "design_font_body": '"Nunito Sans", "Aptos", "Segoe UI", sans-serif',
            "design_color_primary": "#6f9a8d",
            "design_color_secondary": "#e7c3a8",
            "design_color_background": "#f6f8f5",
            "design_color_surface": "#fffdf9",
            "design_color_border": "#d9e2dc",
            "design_color_text": "#2f3a36",
            "design_color_text_soft": "#5a6964",
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
