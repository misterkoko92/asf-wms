import uuid
from decimal import Decimal
from io import BytesIO

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from .catalog import Product
from .inventory import Destination, Location, ProductLot


class ShipmentStatus(models.TextChoices):
    DRAFT = "draft", "Création"
    PICKING = "picking", "En cours"
    PACKED = "packed", "Prêt"
    PLANNED = "planned", "Planifié"
    SHIPPED = "shipped", "Expédié"
    RECEIVED_CORRESPONDENT = "received_correspondent", "Reçu escale"
    DELIVERED = "delivered", "Livré"


TEMP_SHIPMENT_REFERENCE_PREFIX = "EXP-TEMP-"


class Shipment(models.Model):
    reference = models.CharField(max_length=80, unique=True, blank=True)
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        max_length=30, choices=ShipmentStatus.choices, default=ShipmentStatus.DRAFT
    )
    shipper_name = models.CharField(max_length=200)
    shipper_contact_ref = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments_as_shipper",
    )
    shipper_contact = models.CharField(max_length=200, blank=True)
    recipient_name = models.CharField(max_length=200)
    recipient_contact_ref = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments_as_recipient",
    )
    recipient_contact = models.CharField(max_length=200, blank=True)
    correspondent_name = models.CharField(max_length=200, blank=True)
    correspondent_contact_ref = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments_as_correspondent",
    )
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
    is_disputed = models.BooleanField(default=False)
    disputed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipments_closed",
    )
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
        if not self.tracking_token:
            return ""
        return reverse("scan:scan_shipment_track", args=[self.tracking_token])

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

    @staticmethod
    def _merge_update_fields(update_fields, *fields):
        if update_fields is None:
            return None
        merged = set(update_fields)
        merged.update(fields)
        return list(merged)

    def _should_promote_temp_reference(self) -> bool:
        reference = (self.reference or "").strip()
        return (
            bool(reference)
            and reference.startswith(TEMP_SHIPMENT_REFERENCE_PREFIX)
            and self.status != ShipmentStatus.DRAFT
        )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if not self.reference:
            from ..models import generate_shipment_reference

            self.reference = generate_shipment_reference()
            merged_update_fields = self._merge_update_fields(update_fields, "reference")
            if merged_update_fields is not None:
                kwargs["update_fields"] = merged_update_fields
                update_fields = merged_update_fields
        elif self._should_promote_temp_reference():
            from ..models import generate_shipment_reference

            self.reference = generate_shipment_reference()
            merged_update_fields = self._merge_update_fields(update_fields, "reference")
            if merged_update_fields is not None:
                kwargs["update_fields"] = merged_update_fields
        creating = self.pk is None
        if creating and not self.qr_code_image:
            self.generate_qr_code()
        super().save(*args, **kwargs)


class ShipmentTrackingStatus(models.TextChoices):
    PLANNING_OK = "planning_ok", "OK pour planification"
    PLANNED = "planned", "Planifié"
    MOVED_EXPORT = "moved_export", "Déplacé au magasin export"
    BOARDING_OK = "boarding_ok", "OK mise à bord"
    RECEIVED_CORRESPONDENT = "received_correspondent", "Reçu correspondant"
    RECEIVED_RECIPIENT = "received_recipient", "Reçu destinataire"


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
    DRAFT = "draft", "Créé"
    PICKING = "picking", "En préparation"
    PACKED = "packed", "Prêt"
    ASSIGNED = "assigned", "Affecté"
    LABELED = "labeled", "Étiqueté"
    SHIPPED = "shipped", "Expédié"


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


class CartonStatusEvent(models.Model):
    carton = models.ForeignKey(
        Carton,
        on_delete=models.CASCADE,
        related_name="status_events",
    )
    previous_status = models.CharField(max_length=20, choices=CartonStatus.choices)
    new_status = models.CharField(max_length=20, choices=CartonStatus.choices)
    reason = models.CharField(max_length=120, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carton_status_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.carton.code}: {self.previous_status} -> {self.new_status}"


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


class PrintPageFormat(models.TextChoices):
    A4 = "A4", "A4"
    A5 = "A5", "A5"


class PrintPack(models.Model):
    code = models.CharField(max_length=4, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    default_page_format = models.CharField(
        max_length=4,
        choices=PrintPageFormat.choices,
        default=PrintPageFormat.A4,
    )
    fallback_page_format = models.CharField(
        max_length=4,
        choices=PrintPageFormat.choices,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class PrintPackDocument(models.Model):
    pack = models.ForeignKey(
        PrintPack, on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(max_length=60)
    variant = models.CharField(max_length=40, blank=True, default="")
    sequence = models.PositiveIntegerField(default=1)
    xlsx_template_file = models.FileField(
        upload_to="print_pack_templates/",
        null=True,
        blank=True,
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["pack__code", "sequence", "id"]
        unique_together = ("pack", "doc_type", "variant")

    def __str__(self) -> str:
        variant = self.variant or "default"
        return f"{self.pack.code}:{self.doc_type}:{variant}"


class PrintCellMapping(models.Model):
    pack_document = models.ForeignKey(
        PrintPackDocument,
        on_delete=models.CASCADE,
        related_name="cell_mappings",
    )
    worksheet_name = models.CharField(max_length=120)
    cell_ref = models.CharField(max_length=16)
    source_key = models.CharField(max_length=200)
    transform = models.CharField(max_length=80, blank=True)
    required = models.BooleanField(default=False)
    sequence = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pack_document__id", "sequence", "id"]
        unique_together = ("pack_document", "worksheet_name", "cell_ref")

    def __str__(self) -> str:
        return f"{self.pack_document} {self.worksheet_name}!{self.cell_ref}"


class GeneratedPrintArtifactStatus(models.TextChoices):
    GENERATED = "generated", "Generated"
    SYNC_PENDING = "sync_pending", "Sync pending"
    SYNCED = "synced", "Synced"
    SYNC_FAILED = "sync_failed", "Sync failed"
    FAILED = "failed", "Failed"


class GeneratedPrintArtifact(models.Model):
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_print_artifacts",
    )
    carton = models.ForeignKey(
        Carton,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_print_artifacts",
    )
    pack_code = models.CharField(max_length=4)
    status = models.CharField(
        max_length=20,
        choices=GeneratedPrintArtifactStatus.choices,
        default=GeneratedPrintArtifactStatus.GENERATED,
    )
    pdf_file = models.FileField(upload_to="generated_prints/", null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_print_artifacts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    onedrive_path = models.CharField(max_length=500, blank=True)
    sync_attempts = models.PositiveIntegerField(default=0)
    last_sync_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pack_code} ({self.status})"


class GeneratedPrintArtifactItem(models.Model):
    artifact = models.ForeignKey(
        GeneratedPrintArtifact,
        on_delete=models.CASCADE,
        related_name="items",
    )
    doc_type = models.CharField(max_length=60)
    variant = models.CharField(max_length=40, blank=True, default="")
    sequence = models.PositiveIntegerField(default=1)
    source_xlsx_file = models.FileField(
        upload_to="generated_prints/source_xlsx/",
        null=True,
        blank=True,
    )
    generated_pdf_file = models.FileField(
        upload_to="generated_prints/items/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["artifact__id", "sequence", "id"]

    def __str__(self) -> str:
        variant = self.variant or "default"
        return f"{self.artifact_id}:{self.doc_type}:{variant}"
