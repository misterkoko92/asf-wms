from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone


class PlanningParameterSetStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"


class FlightSourceBatchStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IMPORTED = "imported", "Imported"
    FAILED = "failed", "Failed"


class PlanningRunFlightMode(models.TextChoices):
    API = "api", "API"
    EXCEL = "excel", "Excel"
    HYBRID = "hybrid", "Hybrid"


class PlanningRunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    VALIDATING = "validating", "Validating"
    VALIDATION_FAILED = "validation_failed", "Validation failed"
    READY = "ready", "Ready"
    SOLVING = "solving", "Solving"
    SOLVED = "solved", "Solved"
    FAILED = "failed", "Failed"


class PlanningIssueSeverity(models.TextChoices):
    ERROR = "error", "Error"
    WARNING = "warning", "Warning"


class PlanningVersionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    SUPERSEDED = "superseded", "Superseded"
    CANCELLED = "cancelled", "Cancelled"


class PlanningAssignmentSource(models.TextChoices):
    SOLVER = "solver", "Solver"
    MANUAL = "manual", "Manual"
    COPIED = "copied", "Copied"


class CommunicationChannel(models.TextChoices):
    EMAIL = "email", "Email"
    WHATSAPP = "whatsapp", "WhatsApp"


class CommunicationDraftStatus(models.TextChoices):
    GENERATED = "generated", "Generated"
    EDITED = "edited", "Edited"
    EXPORTED = "exported", "Exported"
    SENT_MANUALLY = "sent_manually", "Sent manually"


class PlanningParameterSet(models.Model):
    name = models.CharField(max_length=120, unique=True)
    status = models.CharField(
        max_length=20,
        choices=PlanningParameterSetStatus.choices,
        default=PlanningParameterSetStatus.DRAFT,
    )
    effective_from = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_parameter_sets_created",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_current", "name", "id"]

    def __str__(self) -> str:
        return self.name


class PlanningDestinationRule(models.Model):
    parameter_set = models.ForeignKey(
        PlanningParameterSet,
        on_delete=models.CASCADE,
        related_name="destination_rules",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="planning_destination_rules",
    )
    label = models.CharField(max_length=120, blank=True)
    weekly_frequency = models.PositiveSmallIntegerField(null=True, blank=True)
    max_cartons_per_flight = models.PositiveSmallIntegerField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["parameter_set_id", "priority", "id"]

    def __str__(self) -> str:
        if self.label:
            return self.label
        if self.destination_id:
            return f"Destination rule {self.destination_id}"
        return f"Destination rule {self.pk or 'new'}"


class FlightSourceBatch(models.Model):
    source = models.CharField(max_length=20)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=20,
        choices=FlightSourceBatchStatus.choices,
        default=FlightSourceBatchStatus.DRAFT,
    )
    imported_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-imported_at", "-id"]

    def __str__(self) -> str:
        return f"{self.source} batch {self.pk or 'new'}"


class Flight(models.Model):
    batch = models.ForeignKey(
        FlightSourceBatch,
        on_delete=models.CASCADE,
        related_name="flights",
    )
    flight_number = models.CharField(max_length=40)
    departure_date = models.DateField()
    departure_time = models.TimeField(null=True, blank=True)
    arrival_time = models.TimeField(null=True, blank=True)
    origin_iata = models.CharField(max_length=10, blank=True)
    destination_iata = models.CharField(max_length=10, blank=True)
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_flights",
    )
    capacity_units = models.PositiveIntegerField(null=True, blank=True)
    quality_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["departure_date", "flight_number", "id"]

    def __str__(self) -> str:
        return f"{self.flight_number} {self.departure_date}"


class PlanningRun(models.Model):
    week_start = models.DateField()
    week_end = models.DateField()
    flight_mode = models.CharField(
        max_length=20,
        choices=PlanningRunFlightMode.choices,
        default=PlanningRunFlightMode.HYBRID,
    )
    flight_batch = models.ForeignKey(
        FlightSourceBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_runs",
    )
    parameter_set = models.ForeignKey(
        PlanningParameterSet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_runs",
    )
    status = models.CharField(
        max_length=30,
        choices=PlanningRunStatus.choices,
        default=PlanningRunStatus.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="planning_runs_created",
    )
    validation_summary = models.JSONField(default=dict, blank=True)
    solver_payload = models.JSONField(default=dict, blank=True)
    solver_result = models.JSONField(default=dict, blank=True)
    log_excerpt = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start", "-id"]

    def __str__(self) -> str:
        return f"Planning run {self.week_start} -> {self.week_end}"


class PlanningIssue(models.Model):
    run = models.ForeignKey(
        PlanningRun,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    severity = models.CharField(
        max_length=20,
        choices=PlanningIssueSeverity.choices,
        default=PlanningIssueSeverity.ERROR,
    )
    code = models.CharField(max_length=80, blank=True)
    message = models.TextField()
    source_model = models.CharField(max_length=120, blank=True)
    source_pk = models.PositiveIntegerField(null=True, blank=True)
    context = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "severity", "id"]

    def __str__(self) -> str:
        return self.message[:80]


class PlanningShipmentSnapshot(models.Model):
    run = models.ForeignKey(
        PlanningRun,
        on_delete=models.CASCADE,
        related_name="shipment_snapshots",
    )
    shipment = models.ForeignKey(
        "wms.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_snapshots",
    )
    shipment_reference = models.CharField(max_length=80, blank=True)
    shipper_name = models.CharField(max_length=255, blank=True)
    destination_iata = models.CharField(max_length=10, blank=True)
    priority = models.IntegerField(default=0)
    carton_count = models.PositiveIntegerField(default=0)
    equivalent_units = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "priority", "shipment_reference", "id"]

    def __str__(self) -> str:
        return self.shipment_reference or f"Shipment snapshot {self.pk or 'new'}"


class PlanningVolunteerSnapshot(models.Model):
    run = models.ForeignKey(
        PlanningRun,
        on_delete=models.CASCADE,
        related_name="volunteer_snapshots",
    )
    volunteer = models.ForeignKey(
        "wms.VolunteerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_snapshots",
    )
    volunteer_label = models.CharField(max_length=160, blank=True)
    max_colis_vol = models.PositiveSmallIntegerField(null=True, blank=True)
    availability_summary = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "volunteer_label", "id"]

    def __str__(self) -> str:
        return self.volunteer_label or f"Volunteer snapshot {self.pk or 'new'}"


class PlanningFlightSnapshot(models.Model):
    run = models.ForeignKey(
        PlanningRun,
        on_delete=models.CASCADE,
        related_name="flight_snapshots",
    )
    flight = models.ForeignKey(
        Flight,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_snapshots",
    )
    flight_number = models.CharField(max_length=40)
    departure_date = models.DateField()
    destination_iata = models.CharField(max_length=10, blank=True)
    capacity_units = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "departure_date", "flight_number", "id"]

    def __str__(self) -> str:
        return f"{self.flight_number} {self.departure_date}"


class PlanningVersion(models.Model):
    run = models.ForeignKey(
        PlanningRun,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PlanningVersionStatus.choices,
        default=PlanningVersionStatus.DRAFT,
    )
    based_on = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_versions",
    )
    change_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_versions_created",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run_id", "number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "number"],
                name="unique_planning_version_number_per_run",
            )
        ]

    def __str__(self) -> str:
        return f"Run {self.run_id} version {self.number or '?'}"

    def clean(self):
        super().clean()
        if not self.pk:
            return
        original = (
            type(self)
            .objects.filter(pk=self.pk)
            .values(
                "status",
                "run_id",
                "number",
                "based_on_id",
                "change_reason",
                "published_at",
            )
            .first()
        )
        if not original or original["status"] != PlanningVersionStatus.PUBLISHED:
            return
        immutable_fields = (
            ("run_id", self.run_id),
            ("number", self.number),
            ("based_on_id", self.based_on_id),
            ("change_reason", self.change_reason),
            ("published_at", self.published_at),
            ("status", self.status),
        )
        for field_name, current_value in immutable_fields:
            if original[field_name] != current_value:
                raise ValidationError({"__all__": "Published planning versions are immutable."})

    def save(self, *args, **kwargs):
        if not self.number and self.run_id:
            max_number = (
                type(self)
                .objects.filter(run_id=self.run_id)
                .aggregate(max_number=Max("number"))
                .get("max_number")
                or 0
            )
            self.number = max_number + 1
        if self.status == PlanningVersionStatus.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class PlanningAssignment(models.Model):
    version = models.ForeignKey(
        PlanningVersion,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    shipment_snapshot = models.ForeignKey(
        PlanningShipmentSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    volunteer_snapshot = models.ForeignKey(
        PlanningVolunteerSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    flight_snapshot = models.ForeignKey(
        PlanningFlightSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    assigned_carton_count = models.PositiveIntegerField(default=0)
    assigned_weight_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, default="proposed")
    source = models.CharField(
        max_length=20,
        choices=PlanningAssignmentSource.choices,
        default=PlanningAssignmentSource.SOLVER,
    )
    notes = models.TextField(blank=True)
    sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["version_id", "sequence", "id"]

    def __str__(self) -> str:
        return f"Assignment {self.pk or 'new'}"


class PlanningArtifact(models.Model):
    version = models.ForeignKey(
        PlanningVersion,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    artifact_type = models.CharField(max_length=40)
    label = models.CharField(max_length=120, blank=True)
    file_path = models.CharField(max_length=255, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["version_id", "artifact_type", "id"]

    def __str__(self) -> str:
        return self.label or self.artifact_type


class CommunicationTemplate(models.Model):
    label = models.CharField(max_length=120)
    channel = models.CharField(
        max_length=20,
        choices=CommunicationChannel.choices,
        default=CommunicationChannel.EMAIL,
    )
    scope = models.CharField(max_length=60, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label", "id"]

    def __str__(self) -> str:
        return self.label


class CommunicationDraft(models.Model):
    version = models.ForeignKey(
        PlanningVersion,
        on_delete=models.CASCADE,
        related_name="communication_drafts",
    )
    template = models.ForeignKey(
        CommunicationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drafts",
    )
    channel = models.CharField(
        max_length=20,
        choices=CommunicationChannel.choices,
        default=CommunicationChannel.EMAIL,
    )
    recipient_label = models.CharField(max_length=255, blank=True)
    recipient_contact = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=CommunicationDraftStatus.choices,
        default=CommunicationDraftStatus.GENERATED,
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_communication_drafts_edited",
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["version_id", "channel", "recipient_label", "id"]

    def __str__(self) -> str:
        return f"{self.channel} draft {self.pk or 'new'}"
