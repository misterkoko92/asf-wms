import re
import unicodedata
import uuid
from decimal import Decimal
from io import BytesIO

import qrcode
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import IntegrityError, connection, models, transaction
from django.db.models import F
from django.db.models.functions import Length
from django.urls import reverse
from django.utils import timezone


class ProductCategory(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        unique_together = ("parent", "name")
        ordering = ["name"]
        verbose_name = "Product category"
        verbose_name_plural = "Product categories"

    def __str__(self) -> str:
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name


class ProductTag(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Product"
        verbose_name_plural = "Product List"

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=120, blank=True)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True
    )
    tags = models.ManyToManyField(ProductTag, blank=True)
    barcode = models.CharField(max_length=80, blank=True)
    qr_code_image = models.ImageField(upload_to="qr_codes/", blank=True)
    default_location = models.ForeignKey(
        "Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="default_products",
    )

    length_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    width_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    height_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    weight_g = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    volume_cm3 = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )

    storage_conditions = models.CharField(max_length=200, blank=True)
    perishable = models.BooleanField(default=False)
    quarantine_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"

    def generate_sku(self) -> str:
        prefix = getattr(settings, "SKU_PREFIX", "ASF")
        temp = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{temp}"

    def generate_qr_code(self):
        if not self.sku:
            return
        qr = qrcode.QRCode(border=2)
        qr.add_data(self.sku)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        filename = f"qr_{self.sku}.png"
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if not self.sku:
            self.sku = self.generate_sku()
        if creating and not self.qr_code_image:
            self.generate_qr_code()
        super().save(*args, **kwargs)


class ProductKitItem(models.Model):
    kit = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="kit_items"
    )
    component = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="kit_components"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        unique_together = ("kit", "component")
        ordering = ["kit", "component"]
        verbose_name = "Product kit item"
        verbose_name_plural = "Product kit items"

    def clean(self):
        if self.kit_id and self.component_id and self.kit_id == self.component_id:
            raise ValidationError("Un kit ne peut pas contenir le produit lui-meme.")
        if self.component_id and self.component.kit_items.exists():
            raise ValidationError("Un composant ne peut pas etre un kit.")


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


class ShipmentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PICKING = "picking", "Picking"
    PACKED = "packed", "Packed"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"


class Shipment(models.Model):
    reference = models.CharField(max_length=80, unique=True, blank=True)
    status = models.CharField(
        max_length=20, choices=ShipmentStatus.choices, default=ShipmentStatus.DRAFT
    )
    shipper_name = models.CharField(max_length=200)
    shipper_contact = models.CharField(max_length=200, blank=True)
    recipient_name = models.CharField(max_length=200)
    recipient_contact = models.CharField(max_length=200, blank=True)
    correspondent_name = models.CharField(max_length=200, blank=True)
    destination = models.ForeignKey(
        Destination,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="shipments",
    )
    destination_address = models.TextField()
    destination_country = models.CharField(max_length=80, default="France")
    requested_delivery_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    qr_code_image = models.ImageField(upload_to="qr_codes/shipments/", blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.reference

    def get_tracking_path(self) -> str:
        if not self.reference:
            return ""
        return reverse("scan:scan_shipment_track", args=[self.reference])

    def get_tracking_url(self, request=None) -> str:
        path = self.get_tracking_path()
        if not path:
            return ""
        if request is not None:
            return request.build_absolute_uri(path)
        base_url = getattr(settings, "SITE_BASE_URL", "").strip()
        if base_url:
            if not base_url.startswith(("http://", "https://")):
                base_url = f"https://{base_url}"
            return f"{base_url.rstrip('/')}{path}"
        return path

    def generate_qr_code(self, *, request=None) -> None:
        payload = self.get_tracking_url(request=request)
        if not payload:
            return
        qr = qrcode.QRCode(border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        filename = f"qr_shipment_{self.reference}.png"
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)

    def ensure_qr_code(self, *, request=None) -> None:
        if self.qr_code_image:
            return
        self.generate_qr_code(request=request)
        if self.qr_code_image:
            self.save(update_fields=["qr_code_image"])

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_shipment_reference()
        creating = self.pk is None
        if creating and not self.qr_code_image:
            self.generate_qr_code()
        super().save(*args, **kwargs)


class ShipmentTrackingStatus(models.TextChoices):
    PLANNING_OK = "planning_ok", "OK pour planification"
    PLANNED = "planned", "Planifie"
    MOVED_EXPORT = "moved_export", "Deplace au magasin export"
    BOARDING_OK = "boarding_ok", "OK mise a bord"
    RECEIVED_CORRESPONDENT = "received_correspondent", "Recu correspondant"
    RECEIVED_RECIPIENT = "received_recipient", "Recu destinataire"


class ShipmentTrackingEvent(models.Model):
    shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name="tracking_events"
    )
    status = models.CharField(max_length=40, choices=ShipmentTrackingStatus.choices)
    actor_name = models.CharField(max_length=120)
    actor_structure = models.CharField(max_length=120)
    comments = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.shipment} - {self.get_status_display()}"


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RESERVED = "reserved", "Reserved"
    PREPARING = "preparing", "Preparing"
    READY = "ready", "Ready"
    CANCELLED = "cancelled", "Cancelled"


class Order(models.Model):
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.DRAFT
    )
    public_link = models.ForeignKey(
        "PublicOrderLink",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    association_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders_as_association",
    )
    shipper_name = models.CharField(max_length=200)
    recipient_name = models.CharField(max_length=200)
    correspondent_name = models.CharField(max_length=200, blank=True)
    shipper_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders_as_shipper",
    )
    recipient_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders_as_recipient",
    )
    correspondent_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders_as_correspondent",
    )
    destination_address = models.TextField()
    destination_city = models.CharField(max_length=120, blank=True)
    destination_country = models.CharField(max_length=80, default="France")
    requested_delivery_date = models.DateField(null=True, blank=True)
    shipment = models.OneToOneField(
        Shipment, on_delete=models.SET_NULL, null=True, blank=True, related_name="order"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.reference or f"Order {self.id}"


class PublicOrderLink(models.Model):
    label = models.CharField(max_length=200, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.label or f"Lien commande {self.token}"


class PublicAccountRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class PublicAccountRequest(models.Model):
    link = models.ForeignKey(
        PublicOrderLink, on_delete=models.SET_NULL, null=True, blank=True
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=PublicAccountRequestStatus.choices,
        default=PublicAccountRequestStatus.PENDING,
    )
    association_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, default="France")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.association_name} ({self.get_status_display()})"


class AssociationProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="association_profile"
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="association_profiles",
    )
    notification_emails = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.contact} - {self.user}"

    def get_notification_emails(self) -> list[str]:
        raw = self.notification_emails or ""
        emails = []
        for item in raw.replace("\n", ",").split(","):
            value = item.strip()
            if value:
                emails.append(value)
        return emails


class AssociationRecipient(models.Model):
    association_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.CASCADE,
        related_name="association_recipients",
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, default="France")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["association_contact__name", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.association_contact})"


class DocumentReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class AccountDocumentType(models.TextChoices):
    STATUTES = "statutes", "Statuts"
    REGISTRATION_PROOF = "registration_proof", "Preuve enregistrement"
    ACTIVITY_REPORT = "activity_report", "Rapport d'activite"
    OTHER = "other", "Autre"


class AccountDocument(models.Model):
    association_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.CASCADE,
        related_name="account_documents",
        null=True,
        blank=True,
    )
    account_request = models.ForeignKey(
        PublicAccountRequest,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )
    doc_type = models.CharField(max_length=40, choices=AccountDocumentType.choices)
    status = models.CharField(
        max_length=20,
        choices=DocumentReviewStatus.choices,
        default=DocumentReviewStatus.PENDING,
    )
    file = models.FileField(upload_to="account_documents/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_documents_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} - {self.status}"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    reserved_quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    prepared_quantity = models.IntegerField(
        default=0, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["order", "product"]
        unique_together = ("order", "product")

    def clean(self):
        super().clean()
        errors = {}
        if self.reserved_quantity > self.quantity:
            errors["reserved_quantity"] = "Quantite reservee superieure a la quantite demandee."
        if self.prepared_quantity > self.quantity:
            errors["prepared_quantity"] = "Quantite preparee superieure a la quantite demandee."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.order} - {self.product} ({self.quantity})"

    @property
    def remaining_quantity(self) -> int:
        return max(0, self.quantity - self.prepared_quantity)


class OrderReservation(models.Model):
    order_line = models.ForeignKey(
        OrderLine, on_delete=models.CASCADE, related_name="reservations"
    )
    product_lot = models.ForeignKey(ProductLot, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_line", "product_lot"]

    def __str__(self) -> str:
        return f"{self.order_line} - {self.product_lot} ({self.quantity})"


class OrderDocumentType(models.TextChoices):
    DONATION_ATTESTATION = "donation_attestation", "Attestation donation"
    HUMANITARIAN_ATTESTATION = "humanitarian_attestation", "Attestation aide humanitaire"
    INVOICE = "invoice", "Facture"
    OTHER = "other", "Autre"


class OrderDocument(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=40, choices=OrderDocumentType.choices)
    status = models.CharField(
        max_length=20,
        choices=DocumentReviewStatus.choices,
        default=DocumentReviewStatus.PENDING,
    )
    file = models.FileField(upload_to="order_documents/")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_documents_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} - {self.order}"


class CartonFormat(models.Model):
    name = models.CharField(max_length=120)
    length_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    width_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    height_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    max_weight_g = models.IntegerField(default=8000, validators=[MinValueValidator(1)])
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return (
            f"{self.name} "
            f"({self.length_cm}x{self.width_cm}x{self.height_cm} cm, "
            f"{self.max_weight_g} g)"
        )

    def save(self, *args, **kwargs):
        if self.is_default:
            CartonFormat.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CartonStatus(models.TextChoices):
    DRAFT = "draft", "Cree"
    PICKING = "picking", "En preparation"
    PACKED = "packed", "Pret"
    SHIPPED = "shipped", "Expedie"


class Carton(models.Model):
    code = models.CharField(max_length=80, unique=True)
    status = models.CharField(
        max_length=20, choices=CartonStatus.choices, default=CartonStatus.DRAFT
    )
    length_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    width_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    height_cm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    current_location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True
    )
    shipment = models.ForeignKey(
        Shipment, on_delete=models.SET_NULL, null=True, blank=True
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.code


class CartonItem(models.Model):
    carton = models.ForeignKey(Carton, on_delete=models.CASCADE)
    product_lot = models.ForeignKey(ProductLot, on_delete=models.PROTECT)
    quantity = models.IntegerField()

    class Meta:
        unique_together = ("carton", "product_lot")

    def __str__(self) -> str:
        return f"{self.carton} - {self.product_lot}"


class MovementType(models.TextChoices):
    IN = "in", "In"
    OUT = "out", "Out"
    TRANSFER = "transfer", "Transfer"
    ADJUST = "adjust", "Adjust"
    PRECONDITION = "precondition", "Precondition"
    UNPACK = "unpack", "Unpack"


class StockMovement(models.Model):
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_lot = models.ForeignKey(ProductLot, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    from_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="moves_from",
    )
    to_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="moves_to",
    )
    reason_code = models.CharField(max_length=80, blank=True)
    reason_notes = models.TextField(blank=True)
    related_carton = models.ForeignKey(
        Carton, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_shipment = models.ForeignKey(
        Shipment, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.product} ({self.quantity})"


class DocumentType(models.TextChoices):
    DONATION_CERTIFICATE = "donation_certificate", "Donation certificate"
    HUMANITARIAN_CERTIFICATE = "humanitarian_certificate", "Humanitarian certificate"
    CUSTOMS = "customs", "Customs"
    SHIPMENT_NOTE = "shipment_note", "Shipment note"
    PACKING_LIST_CARTON = "packing_list_carton", "Packing list carton"
    PACKING_LIST_SHIPMENT = "packing_list_shipment", "Packing list shipment"
    ADDITIONAL = "additional", "Document additionnel"


class Document(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=40, choices=DocumentType.choices)
    file = models.FileField(upload_to="documents/", null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.doc_type} - {self.shipment}"


class PrintTemplate(models.Model):
    doc_type = models.CharField(max_length=60, unique=True)
    layout = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["doc_type"]

    def __str__(self) -> str:
        return self.doc_type


class PrintTemplateVersion(models.Model):
    template = models.ForeignKey(
        PrintTemplate, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField()
    layout = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("template", "version")

    def __str__(self) -> str:
        return f"{self.template.doc_type} v{self.version}"


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


RECEIPT_REFERENCE_RE = re.compile(
    r"^(?P<year>\d{2})-(?P<seq>\d{2,})-(?P<donor>[A-Z0-9]{3})-(?P<count>\d{2,})$"
)


def normalize_reference_fragment(value: str, length: int) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch for ch in ascii_value if ch.isalnum())
    cleaned = cleaned.upper()
    if not cleaned:
        cleaned = "X" * length
    if len(cleaned) < length:
        cleaned = cleaned.ljust(length, "X")
    return cleaned[:length]


def generate_receipt_reference(*, received_on=None, source_contact=None) -> str:
    received_on = received_on or timezone.localdate()
    year = received_on.year
    year_prefix = f"{year % 100:02d}"
    donor_code = normalize_reference_fragment(
        source_contact.name if source_contact else "", 3
    )
    with transaction.atomic():
        try:
            sequence_query = ReceiptSequence.objects.filter(year=year)
            if connection.features.has_select_for_update:
                sequence_query = sequence_query.select_for_update()
            sequence = sequence_query.get()
        except ReceiptSequence.DoesNotExist:
            last_number = 0
            references = Receipt.objects.filter(
                reference__startswith=f"{year_prefix}-"
            ).values_list("reference", flat=True)
            for reference in references:
                match = RECEIPT_REFERENCE_RE.match(reference or "")
                if not match:
                    continue
                try:
                    number = int(match.group("seq"))
                except (TypeError, ValueError):
                    continue
                if number > last_number:
                    last_number = number
            if last_number == 0:
                last_number = Receipt.objects.filter(received_on__year=year).count()
            try:
                sequence = ReceiptSequence.objects.create(
                    year=year,
                    last_number=last_number,
                )
            except IntegrityError:
                sequence_query = ReceiptSequence.objects.filter(year=year)
                if connection.features.has_select_for_update:
                    sequence_query = sequence_query.select_for_update()
                sequence = sequence_query.get()
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])

        donor_number = 0
        if source_contact:
            try:
                donor_query = ReceiptDonorSequence.objects.filter(
                    year=year, donor=source_contact
                )
                if connection.features.has_select_for_update:
                    donor_query = donor_query.select_for_update()
                donor_sequence = donor_query.get()
            except ReceiptDonorSequence.DoesNotExist:
                donor_last_number = 0
                donor_refs = Receipt.objects.filter(
                    source_contact=source_contact, received_on__year=year
                ).values_list("reference", flat=True)
                for reference in donor_refs:
                    match = RECEIPT_REFERENCE_RE.match(reference or "")
                    if not match:
                        continue
                    try:
                        number = int(match.group("count"))
                    except (TypeError, ValueError):
                        continue
                    if number > donor_last_number:
                        donor_last_number = number
                if donor_last_number == 0:
                    donor_last_number = Receipt.objects.filter(
                        source_contact=source_contact, received_on__year=year
                    ).count()
                try:
                    donor_sequence = ReceiptDonorSequence.objects.create(
                        year=year,
                        donor=source_contact,
                        last_number=donor_last_number,
                    )
                except IntegrityError:
                    donor_query = ReceiptDonorSequence.objects.filter(
                        year=year, donor=source_contact
                    )
                    if connection.features.has_select_for_update:
                        donor_query = donor_query.select_for_update()
                    donor_sequence = donor_query.get()
            donor_sequence.last_number += 1
            donor_sequence.save(update_fields=["last_number"])
            donor_number = donor_sequence.last_number

    return f"{year_prefix}-{sequence.last_number:02d}-{donor_code}-{donor_number:02d}"


def generate_shipment_reference() -> str:
    year = timezone.localdate().year
    year_prefix = f"{year % 100:02d}"
    with transaction.atomic():
        try:
            sequence_query = ShipmentSequence.objects.filter(year=year)
            if connection.features.has_select_for_update:
                sequence_query = sequence_query.select_for_update()
            sequence = sequence_query.get()
        except ShipmentSequence.DoesNotExist:
            last_ref = (
                Shipment.objects.annotate(ref_len=Length("reference"))
                .filter(reference__startswith=year_prefix, ref_len=6)
                .order_by("-reference")
                .values_list("reference", flat=True)
                .first()
            )
            last_number = 0
            if last_ref and last_ref.isdigit():
                last_number = int(last_ref[2:])
            try:
                sequence = ShipmentSequence.objects.create(
                    year=year,
                    last_number=last_number,
                )
            except IntegrityError:
                sequence_query = ShipmentSequence.objects.filter(year=year)
                if connection.features.has_select_for_update:
                    sequence_query = sequence_query.select_for_update()
                sequence = sequence_query.get()
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
        return f"{year_prefix}{sequence.last_number:04d}"
