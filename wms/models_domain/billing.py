from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class AssociationBillingFrequency(models.TextChoices):
    PER_SHIPMENT = "per_shipment", "Per shipment"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    HALF_YEARLY = "half_yearly", "Half-yearly"
    YEARLY = "yearly", "Yearly"


class AssociationBillingGroupingMode(models.TextChoices):
    SINGLE_DOCUMENT = "single_document", "Single document"
    PER_SHIPMENT = "per_shipment", "Per shipment document"


class AssociationBillingChangeRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class BillingBaseUnitSource(models.TextChoices):
    SHIPPED_UNITS = "shipped_units", "Shipped units"
    ALLOCATED_RECEIVED_UNITS = "allocated_received_units", "Allocated received units"
    MANUAL = "manual", "Manual"


class BillingExtraUnitMode(models.TextChoices):
    NONE = "none", "None"
    SHIPPED_MINUS_ALLOCATED_RECEIVED = (
        "shipped_minus_allocated_received",
        "Shipped minus allocated received",
    )
    MANUAL = "manual", "Manual"


class BillingDocumentKind(models.TextChoices):
    QUOTE = "quote", "Quote"
    INVOICE = "invoice", "Invoice"
    CREDIT_NOTE = "credit_note", "Credit note"


class BillingDocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    CANCELLED = "cancelled", "Cancelled"


class BillingPaymentMethod(models.TextChoices):
    BANK_TRANSFER = "bank_transfer", "Bank transfer"
    CHECK = "check", "Check"
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    OTHER = "other", "Other"


class BillingIssueStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"


class BillingComputationProfile(models.Model):
    code = models.CharField(max_length=50, unique=True)
    label = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    applies_when_receipts_linked = models.BooleanField(null=True, blank=True)
    base_unit_source = models.CharField(
        max_length=40,
        choices=BillingBaseUnitSource.choices,
        default=BillingBaseUnitSource.SHIPPED_UNITS,
    )
    base_step_size = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    base_step_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    extra_unit_mode = models.CharField(
        max_length=50,
        choices=BillingExtraUnitMode.choices,
        default=BillingExtraUnitMode.NONE,
    )
    extra_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    allow_manual_override = models.BooleanField(default=False)
    is_default_for_shipment_only = models.BooleanField(default=False)
    is_default_for_receipt_linked = models.BooleanField(default=False)

    class Meta:
        ordering = ["label", "code"]

    def __str__(self) -> str:
        return self.label


class AssociationBillingProfile(models.Model):
    association_profile = models.OneToOneField(
        "wms.AssociationProfile",
        on_delete=models.CASCADE,
        related_name="billing_profile",
    )
    billing_frequency = models.CharField(
        max_length=30,
        choices=AssociationBillingFrequency.choices,
        default=AssociationBillingFrequency.PER_SHIPMENT,
    )
    grouping_mode = models.CharField(
        max_length=30,
        choices=AssociationBillingGroupingMode.choices,
        default=AssociationBillingGroupingMode.SINGLE_DOCUMENT,
    )
    default_currency = models.CharField(max_length=3, default="EUR")
    default_computation_profile = models.ForeignKey(
        BillingComputationProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="association_defaults",
    )
    billing_name_override = models.CharField(max_length=200, blank=True)
    billing_address_override = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["association_profile_id"]

    def __str__(self) -> str:
        return f"Billing profile for association {self.association_profile_id}"


class AssociationBillingChangeRequest(models.Model):
    association_profile = models.ForeignKey(
        "wms.AssociationProfile",
        on_delete=models.CASCADE,
        related_name="billing_change_requests",
    )
    requested_frequency = models.CharField(
        max_length=30,
        choices=AssociationBillingFrequency.choices,
    )
    requested_grouping_mode = models.CharField(
        max_length=30,
        choices=AssociationBillingGroupingMode.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=AssociationBillingChangeRequestStatus.choices,
        default=AssociationBillingChangeRequestStatus.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billing_change_requests_created",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billing_change_requests_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:
        return f"Billing change request {self.id}"


class BillingServiceCatalogItem(models.Model):
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    service_type = models.CharField(max_length=50, blank=True)
    default_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    default_currency = models.CharField(max_length=3, default="EUR")
    is_discount = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "label"]

    def __str__(self) -> str:
        return self.label


class ShipmentUnitEquivalenceRule(models.Model):
    label = models.CharField(max_length=120)
    category = models.ForeignKey(
        "wms.ProductCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shipment_unit_equivalence_rules",
    )
    applies_to_hors_format = models.BooleanField(default=False)
    units_per_item = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return self.label


class BillingAssociationPriceOverride(models.Model):
    association_billing_profile = models.ForeignKey(
        AssociationBillingProfile,
        on_delete=models.CASCADE,
        related_name="price_overrides",
    )
    service_catalog_item = models.ForeignKey(
        BillingServiceCatalogItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="association_overrides",
    )
    computation_profile = models.ForeignKey(
        BillingComputationProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="association_overrides",
    )
    overridden_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["association_billing_profile_id", "id"]

    def __str__(self) -> str:
        return f"Price override {self.id}"


class ReceiptShipmentAllocation(models.Model):
    receipt = models.ForeignKey(
        "wms.Receipt",
        on_delete=models.CASCADE,
        related_name="shipment_allocations",
    )
    shipment = models.ForeignKey(
        "wms.Shipment",
        on_delete=models.CASCADE,
        related_name="receipt_allocations",
    )
    allocated_received_units = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipt_shipment_allocations_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["receipt_id", "shipment_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "shipment"],
                name="wms_receipt_shipment_allocation_unique_pair",
            )
        ]

    def __str__(self) -> str:
        return f"{self.receipt_id} -> {self.shipment_id}"

    def clean(self):
        super().clean()
        errors = {}
        if self.receipt_id and not self.receipt.source_contact_id:
            errors["receipt"] = "Receipt source association is required."
        if self.shipment_id and not self.shipment.shipper_contact_ref_id:
            errors["shipment"] = "Shipment shipper association is required."
        if (
            self.receipt_id
            and self.shipment_id
            and self.receipt.source_contact_id
            and self.shipment.shipper_contact_ref_id
            and self.receipt.source_contact_id != self.shipment.shipper_contact_ref_id
        ):
            errors["receipt"] = "All linked receipts must belong to the shipment association."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class BillingDocument(models.Model):
    kind = models.CharField(
        max_length=20,
        choices=BillingDocumentKind.choices,
        default=BillingDocumentKind.QUOTE,
    )
    status = models.CharField(
        max_length=20,
        choices=BillingDocumentStatus.choices,
        default=BillingDocumentStatus.DRAFT,
    )
    association_profile = models.ForeignKey(
        "wms.AssociationProfile",
        on_delete=models.PROTECT,
        related_name="billing_documents",
    )
    quote_number = models.CharField(max_length=20, null=True, blank=True, unique=True)
    invoice_number = models.CharField(max_length=20, null=True, blank=True, unique=True)
    credit_note_number = models.CharField(max_length=20, null=True, blank=True, unique=True)
    computation_profile = models.ForeignKey(
        BillingComputationProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    currency = models.CharField(max_length=3, default="EUR")
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )
    source_quote = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_documents",
    )
    issued_snapshot = models.JSONField(default=dict, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        number = self.invoice_number or self.quote_number or self.credit_note_number
        return number or f"Billing document {self.id}"

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.kind == BillingDocumentKind.INVOICE
            and (self.status == BillingDocumentStatus.ISSUED or self.issued_at is not None)
            and not (self.invoice_number or "").strip()
        ):
            errors["invoice_number"] = "Invoice number is required for invoices."
        if errors:
            raise ValidationError(errors)

    def _build_quote_number(self) -> str:
        year = timezone.localdate().year
        prefix = f"DEV-{year}-"
        last_quote_number = (
            BillingDocument.objects.select_for_update()
            .filter(kind=BillingDocumentKind.QUOTE)
            .filter(quote_number__startswith=prefix)
            .exclude(pk=self.pk)
            .order_by("-quote_number")
            .values_list("quote_number", flat=True)
            .first()
        )
        next_number = 1
        if last_quote_number:
            next_number = int(last_quote_number.removeprefix(prefix)) + 1
        return f"{prefix}{next_number:04d}"

    def _normalize_optional_numbers(self):
        self.quote_number = (self.quote_number or "").strip() or None
        self.invoice_number = (self.invoice_number or "").strip() or None
        self.credit_note_number = (self.credit_note_number or "").strip() or None

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._normalize_optional_numbers()
            if self.kind == BillingDocumentKind.QUOTE and not self.quote_number:
                self.quote_number = self._build_quote_number()
            self.full_clean()
            super().save(*args, **kwargs)


class BillingDocumentShipment(models.Model):
    document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="shipment_links",
    )
    shipment = models.ForeignKey(
        "wms.Shipment",
        on_delete=models.CASCADE,
        related_name="billing_document_links",
    )

    class Meta:
        ordering = ["document_id", "shipment_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "shipment"],
                name="wms_billing_document_shipment_unique_pair",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_id} -> shipment {self.shipment_id}"


class BillingDocumentReceipt(models.Model):
    document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="receipt_links",
    )
    receipt = models.ForeignKey(
        "wms.Receipt",
        on_delete=models.CASCADE,
        related_name="billing_document_links",
    )

    class Meta:
        ordering = ["document_id", "receipt_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "receipt"],
                name="wms_billing_document_receipt_unique_pair",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_id} -> receipt {self.receipt_id}"


class BillingDocumentLine(models.Model):
    document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_number = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    service_catalog_item = models.ForeignKey(
        BillingServiceCatalogItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_lines",
    )
    is_manual = models.BooleanField(default=False)

    class Meta:
        ordering = ["document_id", "line_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "line_number"],
                name="wms_billing_document_line_unique_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_id} line {self.line_number}"


class BillingPayment(models.Model):
    document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    paid_on = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(
        max_length=30,
        choices=BillingPaymentMethod.choices,
        default=BillingPaymentMethod.BANK_TRANSFER,
    )
    reference = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)
    proof_attachment = models.FileField(upload_to="billing/payments/", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billing_payments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "paid_on", "id"]

    def __str__(self) -> str:
        return f"Payment {self.id} for {self.document_id}"


class BillingIssue(models.Model):
    document = models.ForeignKey(
        BillingDocument,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    status = models.CharField(
        max_length=20,
        choices=BillingIssueStatus.choices,
        default=BillingIssueStatus.OPEN,
    )
    description = models.TextField()
    resolution_comment = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billing_issues_reported",
    )
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billing_issues_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self) -> str:
        return f"Billing issue {self.id}"


@receiver(post_save, sender="wms.AssociationProfile")
def ensure_association_billing_profile(sender, instance, **kwargs):
    AssociationBillingProfile.objects.get_or_create(association_profile=instance)
