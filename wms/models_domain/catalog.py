import uuid
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

import qrcode
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import models

from ..text_utils import normalize_category_name, normalize_title, normalize_upper


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

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.name:
            normalized = normalize_category_name(
                self.name, is_root=self.parent_id is None
            )
            if normalized != self.name:
                self.name = normalized
                if update_fields is not None:
                    update_fields = set(update_fields)
                    update_fields.add("name")
                    kwargs["update_fields"] = list(update_fields)
        super().save(*args, **kwargs)


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
    color = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="product_photos/", blank=True)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.PROTECT, null=True, blank=True
    )
    tags = models.ManyToManyField(ProductTag, blank=True)
    barcode = models.CharField(max_length=80, blank=True)
    ean = models.CharField(max_length=32, blank=True)
    pu_ht = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tva = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="TVA en taux (ex: 0.2 pour 20%).",
    )
    pu_ttc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
    )
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

    def _compute_pu_ttc(self):
        if self.pu_ht is None or self.tva is None:
            return None
        tva_rate = self.tva
        if tva_rate > Decimal("1"):
            tva_rate = (tva_rate / Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        return (self.pu_ht * (Decimal("1") + tva_rate)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        update_set = set(update_fields) if update_fields is not None else None
        creating = self.pk is None
        if self.name:
            normalized = normalize_title(self.name)
            if normalized != self.name:
                self.name = normalized
                if update_set is not None:
                    update_set.add("name")
        if self.brand:
            normalized = normalize_upper(self.brand)
            if normalized != self.brand:
                self.brand = normalized
                if update_set is not None:
                    update_set.add("brand")
        if not self.sku:
            self.sku = self.generate_sku()
        if creating and not self.qr_code_image:
            self.generate_qr_code()
        if self.tva is not None and self.tva > Decimal("1"):
            normalized = (self.tva / Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            if normalized != self.tva:
                self.tva = normalized
                if update_set is not None:
                    update_set.add("tva")
        computed_ttc = self._compute_pu_ttc()
        if computed_ttc != self.pu_ttc:
            self.pu_ttc = computed_ttc
            if update_set is not None:
                update_set.add("pu_ttc")
        if update_set is not None:
            kwargs["update_fields"] = list(update_set)
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

    def _component_reaches_kit(self):
        if not self.kit_id or not self.component_id:
            return False
        visited = set()
        to_visit = [self.component_id]
        descendants = ProductKitItem.objects.all()
        if self.pk:
            descendants = descendants.exclude(pk=self.pk)
        while to_visit:
            current_id = to_visit.pop()
            if current_id == self.kit_id:
                return True
            if current_id in visited:
                continue
            visited.add(current_id)
            to_visit.extend(
                descendants.filter(kit_id=current_id).values_list("component_id", flat=True)
            )
        return False

    def clean(self):
        if self.kit_id and self.component_id and self.kit_id == self.component_id:
            raise ValidationError("Un kit ne peut pas contenir le produit lui-meme.")
        if self._component_reaches_kit():
            raise ValidationError("Un kit ne peut pas contenir indirectement lui-meme.")
