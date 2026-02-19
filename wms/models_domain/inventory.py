from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from ..text_utils import normalize_upper
from .catalog import Product


class Warehouse(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Location(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    zone = models.CharField(max_length=40)
    aisle = models.CharField(max_length=40)
    shelf = models.CharField(max_length=40)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("warehouse", "zone", "aisle", "shelf")
        ordering = ["warehouse", "zone", "aisle", "shelf"]

    def __str__(self) -> str:
        return f"{self.warehouse} {self.zone}-{self.aisle}-{self.shelf}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        update_set = set(update_fields) if update_fields is not None else None
        if self.zone:
            normalized = normalize_upper(self.zone)
            if normalized != self.zone:
                self.zone = normalized
                if update_set is not None:
                    update_set.add("zone")
        if self.aisle:
            normalized = normalize_upper(self.aisle)
            if normalized != self.aisle:
                self.aisle = normalized
                if update_set is not None:
                    update_set.add("aisle")
        if self.shelf:
            normalized = normalize_upper(self.shelf)
            if normalized != self.shelf:
                self.shelf = normalized
                if update_set is not None:
                    update_set.add("shelf")
        if update_set is not None:
            kwargs["update_fields"] = list(update_set)
        super().save(*args, **kwargs)


class RackColor(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    zone = models.CharField(max_length=40)
    color = models.CharField(max_length=40)

    class Meta:
        unique_together = ("warehouse", "zone")
        ordering = ["warehouse", "zone"]

    def __str__(self) -> str:
        return f"{self.warehouse} {self.zone} - {self.color}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.zone:
            normalized = normalize_upper(self.zone)
            if normalized != self.zone:
                self.zone = normalized
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add("zone")
                    kwargs["update_fields"] = list(update_fields)
        super().save(*args, **kwargs)


class ProductLotStatus(models.TextChoices):
    QUARANTINED = "quarantined", "Quarantined"
    AVAILABLE = "available", "Available"
    HOLD = "hold", "Hold"
    EXPIRED = "expired", "Expired"


class ProductLot(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    lot_code = models.CharField(max_length=80, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    received_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=ProductLotStatus.choices, default=ProductLotStatus.AVAILABLE
    )
    quantity_on_hand = models.IntegerField(default=0)
    quantity_reserved = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    source_receipt = models.ForeignKey(
        "Receipt",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="product_lots",
    )
    storage_conditions = models.CharField(max_length=200, blank=True)
    quarantine_reason = models.TextField(blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["product", "expires_on"]
        verbose_name = "Product Availability"
        verbose_name_plural = "Product Availability"

    def __str__(self) -> str:
        return f"{self.product} ({self.lot_code or 'lot'})"


class ReceiptType(models.TextChoices):
    DONATION = "donation", "Donation"
    PALLET = "pallet", "Pallet"
    ASSOCIATION = "association", "Association"
    OTHER = "other", "Other"


class ReceiptStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class Receipt(models.Model):
    reference = models.CharField(max_length=80, blank=True)
    receipt_type = models.CharField(
        max_length=20, choices=ReceiptType.choices, default=ReceiptType.DONATION
    )
    status = models.CharField(
        max_length=20, choices=ReceiptStatus.choices, default=ReceiptStatus.DRAFT
    )
    source_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipts_as_source",
    )
    carrier_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="receipts_as_carrier",
    )
    origin_reference = models.CharField(max_length=120, blank=True)
    carrier_reference = models.CharField(max_length=120, blank=True)
    pallet_count = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    carton_count = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    hors_format_count = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    transport_request_date = models.DateField(null=True, blank=True)
    received_on = models.DateField(default=timezone.localdate)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_on", "-created_at"]

    def __str__(self) -> str:
        return self.reference or f"Receipt {self.id}"

    def save(self, *args, **kwargs):
        if not self.reference:
            from ..models import generate_receipt_reference

            self.reference = generate_receipt_reference(
                received_on=self.received_on,
                source_contact=self.source_contact,
            )
        super().save(*args, **kwargs)


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    lot_code = models.CharField(max_length=80, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    lot_status = models.CharField(
        max_length=20, choices=ProductLotStatus.choices, blank=True, default=""
    )
    location = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True)
    storage_conditions = models.CharField(max_length=200, blank=True)
    received_lot = models.ForeignKey(
        ProductLot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_lines",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["receipt", "product"]

    def __str__(self) -> str:
        return f"{self.receipt} - {self.product} ({self.quantity})"

    @property
    def is_received(self) -> bool:
        return self.received_lot_id is not None


class ReceiptHorsFormat(models.Model):
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, related_name="hors_format_items"
    )
    line_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    description = models.TextField()

    class Meta:
        ordering = ["receipt", "line_number"]
        unique_together = ("receipt", "line_number")

    def __str__(self) -> str:
        return f"{self.receipt} - Hors format {self.line_number}"


class ReceiptSequence(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["year"]

    def __str__(self) -> str:
        return f"{self.year}: {self.last_number}"


class ReceiptDonorSequence(models.Model):
    year = models.PositiveSmallIntegerField()
    donor = models.ForeignKey("contacts.Contact", on_delete=models.PROTECT)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["year", "donor__name"]
        unique_together = ("year", "donor")

    def __str__(self) -> str:
        return f"{self.year} {self.donor}: {self.last_number}"


class ShipmentSequence(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["year"]

    def __str__(self) -> str:
        return f"{self.year}: {self.last_number}"


class Destination(models.Model):
    city = models.CharField(max_length=120)
    iata_code = models.CharField(max_length=10, unique=True)
    country = models.CharField(max_length=80)
    correspondent_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="destinations_as_correspondent",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city"]
        unique_together = ("city", "country")

    def __str__(self) -> str:
        label = self.city
        if self.iata_code:
            label = f"{label} ({self.iata_code})"
        if self.country:
            label = f"{label} - {self.country}"
        return label
