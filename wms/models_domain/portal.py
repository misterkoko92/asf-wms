import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .catalog import Product
from .inventory import Destination, ProductLot
from .shipment import Shipment


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RESERVED = "reserved", "Reserved"
    PREPARING = "preparing", "Preparing"
    READY = "ready", "Ready"
    CANCELLED = "cancelled", "Cancelled"


class OrderReviewStatus(models.TextChoices):
    PENDING = "pending_validation", "En attente validation"
    APPROVED = "approved", "Valider"
    REJECTED = "rejected", "Refuser"
    CHANGES_REQUESTED = "changes_requested", "Modifier"


class Order(models.Model):
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.DRAFT
    )
    review_status = models.CharField(
        max_length=30,
        choices=OrderReviewStatus.choices,
        default=OrderReviewStatus.PENDING,
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
    reviewed_at = models.DateTimeField(null=True, blank=True)
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


class PublicAccountRequestType(models.TextChoices):
    ASSOCIATION = "association", "Association"
    USER = "user", "Utilisateur WMS"


class PublicAccountRequest(models.Model):
    link = models.ForeignKey(
        PublicOrderLink, on_delete=models.SET_NULL, null=True, blank=True
    )
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.SET_NULL, null=True, blank=True
    )
    account_type = models.CharField(
        max_length=20,
        choices=PublicAccountRequestType.choices,
        default=PublicAccountRequestType.ASSOCIATION,
        db_index=True,
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
    requested_username = models.CharField(max_length=150, blank=True)
    requested_password_hash = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        if self.account_type == PublicAccountRequestType.USER:
            label = self.requested_username or self.email
            return f"Utilisateur {label} ({self.get_status_display()})"
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
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.contact} - {self.user}"

    def clean(self):
        super().clean()
        errors = {}
        if self.contact_id:
            from contacts.models import ContactType

            if self.contact.contact_type != ContactType.ORGANIZATION:
                errors["contact"] = (
                    "Le contact d'association doit être une organisation."
                )
            elif not self.contact.is_active:
                errors["contact"] = (
                    "Le contact d'association doit être actif."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_notification_emails(self) -> list[str]:
        portal_contacts = getattr(self, "portal_contacts", None) if self.pk else None
        if portal_contacts is not None:
            emails = []
            seen = set()
            for contact in portal_contacts.filter(is_active=True).order_by("position", "id"):
                value = (contact.email or "").strip()
                if not value:
                    continue
                normalized = value.lower()
                if normalized in seen:
                    continue
                seen.add(normalized)
                emails.append(value)
            if emails:
                return emails

        raw = self.notification_emails or ""
        emails = []
        for item in raw.replace("\n", ",").split(","):
            value = item.strip()
            if value:
                emails.append(value)
        return emails


class AssociationContactTitle(models.TextChoices):
    MR = "mr", "M."
    MRS = "mrs", "Mme"
    MS = "ms", "Mlle"
    DR = "dr", "Dr"
    PR = "pr", "Pr"
    PERE = "pere", "Père"
    SOEUR = "soeur", "Sœur"
    FRERE = "frere", "Frère"
    ABBE = "abbe", "Abbé"
    IMAM = "imam", "Imam"
    RABBIN = "rabbin", "Rabbin"
    PASTEUR = "pasteur", "Pasteur"
    EVEQUE = "eveque", "Évêque"
    MONSEIGNEUR = "mons", "Monseigneur"
    PRESIDENT = "president", "Président"
    MINISTRE = "ministre", "Ministre"
    AMBASSADEUR = "ambassad", "Ambassadeur"
    MAIRE = "maire", "Maire"
    PREFET = "prefet", "Préfet"
    GOUVERNEUR = "gouvern", "Gouverneur"
    DEPUTE = "depute", "Député"
    SENATEUR = "senateur", "Sénateur"
    GENERAL = "gen", "Général"
    COLONEL = "colonel", "Colonel"
    COMMANDANT = "cmdt", "Commandant"
    CAPITAINE = "cpt", "Capitaine"
    LIEUTENANT = "lt", "Lieutenant"
    ADJUDANT = "adj", "Adjudant"
    SERGENT = "sgt", "Sergent"


class AssociationPortalContact(models.Model):
    profile = models.ForeignKey(
        AssociationProfile,
        on_delete=models.CASCADE,
        related_name="portal_contacts",
    )
    position = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(
        max_length=10,
        choices=AssociationContactTitle.choices,
        blank=True,
    )
    last_name = models.CharField(max_length=120, blank=True)
    first_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    is_administrative = models.BooleanField(default=False)
    is_shipping = models.BooleanField(default=False)
    is_billing = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(is_administrative=True)
                    | models.Q(is_shipping=True)
                    | models.Q(is_billing=True)
                ),
                name="wms_assoc_portal_contact_has_type",
            )
        ]

    def clean(self):
        super().clean()
        if not (self.is_administrative or self.is_shipping or self.is_billing):
            raise ValidationError(
                {
                    "is_administrative": "Sélectionnez au moins un type de contact.",
                }
            )

    def __str__(self) -> str:
        display = " ".join(
            part for part in [self.get_title_display(), self.first_name, self.last_name] if part
        ).strip()
        return display or self.email or f"Contact portail #{self.pk}"


class AssociationRecipient(models.Model):
    association_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.CASCADE,
        related_name="association_recipients",
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="association_recipients",
    )
    name = models.CharField(max_length=200)
    structure_name = models.CharField(max_length=200, blank=True)
    contact_title = models.CharField(
        max_length=10,
        choices=AssociationContactTitle.choices,
        blank=True,
    )
    contact_last_name = models.CharField(max_length=120, blank=True)
    contact_first_name = models.CharField(max_length=120, blank=True)
    phones = models.TextField(blank=True)
    emails = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, default="France")
    notes = models.TextField(blank=True)
    notify_deliveries = models.BooleanField(default=False)
    is_delivery_contact = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            "association_contact__name",
            "structure_name",
            "name",
            "contact_last_name",
            "contact_first_name",
        ]

    def __str__(self) -> str:
        return f"{self.get_display_name()} ({self.association_contact})"

    @staticmethod
    def _split_multi_values(value: str) -> list[str]:
        raw = (value or "").replace("\n", ";").replace(",", ";")
        return [item.strip() for item in raw.split(";") if item.strip()]

    def get_primary_email(self) -> str:
        values = self._split_multi_values(self.emails)
        if values:
            return values[0]
        return (self.email or "").strip()

    def get_primary_phone(self) -> str:
        values = self._split_multi_values(self.phones)
        if values:
            return values[0]
        return (self.phone or "").strip()

    def get_contact_display_name(self) -> str:
        title = self.get_contact_title_display() if self.contact_title else ""
        last_name = (self.contact_last_name or "").strip()
        if last_name:
            last_name = last_name.upper()
        parts = [title, (self.contact_first_name or "").strip(), last_name]
        return " ".join(part for part in parts if part).strip()

    def get_display_name(self) -> str:
        if (self.structure_name or "").strip():
            return self.structure_name.strip()
        if (self.name or "").strip():
            return self.name.strip()
        contact_display = self.get_contact_display_name()
        if contact_display:
            return contact_display
        return f"Destinataire #{self.pk}" if self.pk else "Destinataire"

    def _normalize_legacy_fields(self):
        if (self.structure_name or "").strip():
            self.name = self.structure_name.strip()
        elif not (self.name or "").strip():
            self.name = self.get_contact_display_name() or "Destinataire"

        primary_email = self.get_primary_email()
        primary_phone = self.get_primary_phone()
        self.email = primary_email[:254]
        self.phone = primary_phone[:40]

    def save(self, *args, **kwargs):
        self._normalize_legacy_fields()
        super().save(*args, **kwargs)


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
            errors["reserved_quantity"] = "Quantité réservée supérieure à la quantité demandée."
        if self.prepared_quantity > self.quantity:
            errors["prepared_quantity"] = "Quantité préparée supérieure à la quantité demandée."
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
