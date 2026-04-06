from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PreparationRunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    GENERATED = "generated", "Generated"
    FROZEN = "frozen", "Frozen"
    CONVERTED = "converted", "Converted"
    CANCELLED = "cancelled", "Cancelled"


class PreparationProposalSource(models.TextChoices):
    DEPOSIT = "deposit", "Deposit"
    ASF_STOCK = "asf_stock", "ASF stock"
    MIXED = "mixed", "Mixed"


class PreparationShipmentProposalStatus(models.TextChoices):
    PROPOSED = "proposed", "Proposed"
    ACCEPTED = "accepted", "Accepted"
    PARTIAL = "partial", "Partial"
    REJECTED = "rejected", "Rejected"
    NEEDS_RECALC = "needs_recalc", "Needs recalc"
    CONVERTED = "converted", "Converted"


class PreparationShipperMode(models.TextChoices):
    DEPOSIT_ONLY = "deposit_only", "Deposit only"
    ASF_COMPLEMENT_ALLOWED = "asf_complement_allowed", "ASF complement allowed"
    ASF_AUTO_ALLOWED = "asf_auto_allowed", "ASF auto allowed"


class PreparationReservationStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    RELEASED = "released", "Released"
    CONSUMED = "consumed", "Consumed"


class PreparationDecisionAction(models.TextChoices):
    ACCEPT = "accept", "Accept"
    REJECT_KEEP_DRAFT = "reject_keep_draft", "Reject and keep draft"
    REJECT_DELETE = "reject_delete", "Reject and delete"
    RECLAIM_FOR_URGENCY = "reclaim_for_urgency", "Reclaim for urgency"


class RecurringPreparationPeriodUnit(models.TextChoices):
    WEEK = "week", "Week"
    MONTH = "month", "Month"


class PreparationParameterSet(models.Model):
    name = models.CharField(max_length=120, unique=True)
    notes = models.TextField(blank=True)
    is_current = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparation_parameter_sets_created",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_current", "name", "id"]

    def __str__(self) -> str:
        return self.name


class PreparationDestinationRule(models.Model):
    parameter_set = models.ForeignKey(
        PreparationParameterSet,
        on_delete=models.CASCADE,
        related_name="destination_rules",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.CASCADE,
        related_name="preparation_destination_rules",
    )
    max_equivalent_units_per_flight = models.PositiveIntegerField(null=True, blank=True)
    max_usable_flights_per_week = models.PositiveIntegerField(null=True, blank=True)
    max_equivalent_units_per_week = models.PositiveIntegerField(null=True, blank=True)
    max_shipments_per_week = models.PositiveIntegerField(null=True, blank=True)
    allowed_weekdays = models.JSONField(default=list, blank=True)
    fairness_weight = models.DecimalField(max_digits=6, decimal_places=2, default="1.00")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["parameter_set_id", "destination__city", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["parameter_set", "destination"],
                name="wms_prep_dest_rule_unique_parameter_destination",
            ),
        ]

    def __str__(self) -> str:
        return str(self.destination)


class PreparationShipperRule(models.Model):
    parameter_set = models.ForeignKey(
        PreparationParameterSet,
        on_delete=models.CASCADE,
        related_name="shipper_rules",
    )
    shipper = models.ForeignKey(
        "wms.ShipmentShipper",
        on_delete=models.CASCADE,
        related_name="preparation_rules",
    )
    mode = models.CharField(
        max_length=32,
        choices=PreparationShipperMode.choices,
        default=PreparationShipperMode.DEPOSIT_ONLY,
    )
    score_coefficient = models.DecimalField(max_digits=6, decimal_places=2, default="1.00")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["parameter_set_id", "shipper_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["parameter_set", "shipper"],
                name="wms_prep_shipper_rule_unique_parameter_shipper",
            ),
        ]

    def __str__(self) -> str:
        return str(self.shipper)


class RecurringPreparationNeed(models.Model):
    shipper = models.ForeignKey(
        "wms.ShipmentShipper",
        on_delete=models.CASCADE,
        related_name="recurring_preparation_needs",
    )
    recipient_organization = models.ForeignKey(
        "wms.ShipmentRecipientOrganization",
        on_delete=models.CASCADE,
        related_name="recurring_preparation_needs",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.CASCADE,
        related_name="recurring_preparation_needs",
    )
    period_unit = models.CharField(
        max_length=16,
        choices=RecurringPreparationPeriodUnit.choices,
        default=RecurringPreparationPeriodUnit.WEEK,
    )
    target_equivalent_units = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_preparation_needs_created",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shipper_id", "recipient_organization_id", "destination_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["shipper", "recipient_organization", "destination"],
                name="wms_recurring_prep_need_unique_scope",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.shipper} -> {self.recipient_organization} ({self.destination})"

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.destination_id
            and self.recipient_organization_id
            and self.recipient_organization.destination_id != self.destination_id
        ):
            errors["destination"] = (
                "The recurring need destination must match the recipient organization destination."
            )
        if errors:
            raise ValidationError(errors)


class PreparationRun(models.Model):
    parameter_set = models.ForeignKey(
        PreparationParameterSet,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="preparation_runs_created",
    )
    target_equivalent_units = models.PositiveIntegerField()
    target_shipment_count = models.PositiveIntegerField()
    target_shipment_size_units = models.PositiveIntegerField(default=10)
    min_shipment_size_units = models.PositiveIntegerField(default=1)
    max_shipment_size_units = models.PositiveIntegerField(null=True, blank=True)
    flight_window_start = models.DateField()
    flight_window_end = models.DateField()
    status = models.CharField(
        max_length=24,
        choices=PreparationRunStatus.choices,
        default=PreparationRunStatus.DRAFT,
    )
    parameter_snapshot = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-flight_window_start", "-id"]

    def __str__(self) -> str:
        return f"Preparation run {self.flight_window_start} -> {self.flight_window_end}"


class PreparationRunNeedSnapshot(models.Model):
    run = models.ForeignKey(
        PreparationRun,
        on_delete=models.CASCADE,
        related_name="need_snapshots",
    )
    recurring_need = models.ForeignKey(
        RecurringPreparationNeed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="run_snapshots",
    )
    shipper = models.ForeignKey(
        "wms.ShipmentShipper",
        on_delete=models.PROTECT,
        related_name="preparation_need_snapshots",
    )
    recipient_organization = models.ForeignKey(
        "wms.ShipmentRecipientOrganization",
        on_delete=models.PROTECT,
        related_name="preparation_need_snapshots",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.PROTECT,
        related_name="preparation_need_snapshots",
    )
    period_unit = models.CharField(max_length=16, choices=RecurringPreparationPeriodUnit.choices)
    target_equivalent_units = models.PositiveIntegerField()
    snapshot_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "shipper_id", "recipient_organization_id", "id"]

    def __str__(self) -> str:
        return f"Need snapshot {self.run_id} / {self.shipper_id}"


class PreparationShipmentProposal(models.Model):
    run = models.ForeignKey(
        PreparationRun,
        on_delete=models.CASCADE,
        related_name="shipment_proposals",
    )
    shipper = models.ForeignKey(
        "wms.ShipmentShipper",
        on_delete=models.PROTECT,
        related_name="preparation_shipment_proposals",
    )
    recipient_organization = models.ForeignKey(
        "wms.ShipmentRecipientOrganization",
        on_delete=models.PROTECT,
        related_name="preparation_shipment_proposals",
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.PROTECT,
        related_name="preparation_shipment_proposals",
    )
    sequence = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=24, choices=PreparationProposalSource.choices)
    status = models.CharField(
        max_length=24,
        choices=PreparationShipmentProposalStatus.choices,
        default=PreparationShipmentProposalStatus.PROPOSED,
    )
    equivalent_units_total = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rationale = models.JSONField(default=dict, blank=True)
    converted_shipment = models.ForeignKey(
        "wms.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparation_proposals",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run_id", "shipper_id", "recipient_organization_id", "sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "shipper", "recipient_organization", "destination", "sequence"],
                name="wms_prep_ship_prop_unique_run_scope_sequence",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Proposal {self.run_id}/{self.shipper_id}/{self.recipient_organization_id}"
            f"/{self.sequence}"
        )


class PreparationCartonProposal(models.Model):
    shipment_proposal = models.ForeignKey(
        PreparationShipmentProposal,
        on_delete=models.CASCADE,
        related_name="carton_proposals",
    )
    product = models.ForeignKey(
        "wms.Product",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preparation_carton_proposals",
    )
    source = models.CharField(max_length=24, choices=PreparationProposalSource.choices)
    status = models.CharField(
        max_length=24,
        choices=PreparationShipmentProposalStatus.choices,
        default=PreparationShipmentProposalStatus.PROPOSED,
    )
    quantity = models.PositiveIntegerField()
    equivalent_units_total = models.PositiveIntegerField(default=0)
    rationale = models.JSONField(default=dict, blank=True)
    converted_carton = models.ForeignKey(
        "wms.Carton",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preparation_proposals",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["shipment_proposal_id", "id"]

    def __str__(self) -> str:
        return f"Carton proposal {self.shipment_proposal_id}/{self.id or 'new'}"


class PreparationReservation(models.Model):
    run = models.ForeignKey(
        PreparationRun,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    shipment_proposal = models.ForeignKey(
        PreparationShipmentProposal,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    carton_proposal = models.ForeignKey(
        PreparationCartonProposal,
        on_delete=models.CASCADE,
        related_name="reservations",
        null=True,
        blank=True,
    )
    product_lot = models.ForeignKey(
        "wms.ProductLot",
        on_delete=models.PROTECT,
        related_name="preparation_reservations",
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=24,
        choices=PreparationReservationStatus.choices,
        default=PreparationReservationStatus.ACTIVE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="preparation_reservations_created",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run_id", "shipment_proposal_id", "id"]

    def __str__(self) -> str:
        return f"Reservation {self.run_id}/{self.product_lot_id}"


class PreparationDecisionLog(models.Model):
    run = models.ForeignKey(
        PreparationRun,
        on_delete=models.CASCADE,
        related_name="decision_logs",
    )
    shipment_proposal = models.ForeignKey(
        PreparationShipmentProposal,
        on_delete=models.CASCADE,
        related_name="decision_logs",
    )
    carton_proposal = models.ForeignKey(
        PreparationCartonProposal,
        on_delete=models.CASCADE,
        related_name="decision_logs",
        null=True,
        blank=True,
    )
    reservation = models.ForeignKey(
        PreparationReservation,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=32, choices=PreparationDecisionAction.choices)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="preparation_decision_logs_created",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run_id", "id"]

    def __str__(self) -> str:
        return f"{self.run_id} {self.action}"
