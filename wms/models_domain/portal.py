import uuid

from django import VERSION as DJANGO_VERSION
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..document_scan import DocumentScanStatus
from .catalog import Product
from .inventory import Destination, ProductLot
from .shipment import Shipment


def _check_constraint_compat(*, condition, name):
    constraint_kwargs = {"name": name}
    if DJANGO_VERSION >= (5, 1):
        constraint_kwargs["condition"] = condition
    else:
        constraint_kwargs["check"] = condition
    return models.CheckConstraint(**constraint_kwargs)


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
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.DRAFT)
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
    link = models.ForeignKey(PublicOrderLink, on_delete=models.SET_NULL, null=True, blank=True)
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
                errors["contact"] = "Le contact d'association doit être une organisation."
            elif not self.contact.is_active:
                errors["contact"] = "Le contact d'association doit être actif."
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
    MR = "mr", _("M.")
    MRS = "mrs", _("Mme")
    MS = "ms", _("Mlle")
    DR = "dr", _("Dr")
    PR = "pr", _("Pr")
    PERE = "pere", _("Père")
    SOEUR = "soeur", _("Sœur")
    FRERE = "frere", _("Frère")
    ABBE = "abbe", _("Abbé")
    IMAM = "imam", _("Imam")
    RABBIN = "rabbin", _("Rabbin")
    PASTEUR = "pasteur", _("Pasteur")
    EVEQUE = "eveque", _("Évêque")
    MONSEIGNEUR = "mons", _("Monseigneur")
    PRESIDENT = "president", _("Président")
    MINISTRE = "ministre", _("Ministre")
    AMBASSADEUR = "ambassad", _("Ambassadeur")
    MAIRE = "maire", _("Maire")
    PREFET = "prefet", _("Préfet")
    GOUVERNEUR = "gouvern", _("Gouverneur")
    DEPUTE = "depute", _("Député")
    SENATEUR = "senateur", _("Sénateur")
    GENERAL = "gen", _("Général")
    COLONEL = "colonel", _("Colonel")
    COMMANDANT = "cmdt", _("Commandant")
    CAPITAINE = "cpt", _("Capitaine")
    LIEUTENANT = "lt", _("Lieutenant")
    ADJUDANT = "adj", _("Adjudant")
    SERGENT = "sgt", _("Sergent")


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
            _check_constraint_compat(
                condition=(
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
    synced_contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="synced_portal_recipients",
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

    def get_shipment_party_display_name(self) -> str:
        structure_name = (self.structure_name or self.name or "").strip()
        contact_display = self.get_contact_display_name()
        if (
            structure_name
            and contact_display
            and structure_name.casefold() != contact_display.casefold()
        ):
            return f"{contact_display}, {structure_name}"
        return structure_name or contact_display or self.get_display_name()

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
    scan_status = models.CharField(
        max_length=20,
        choices=DocumentScanStatus.choices,
        default=DocumentScanStatus.CLEAN,
    )
    scan_message = models.CharField(max_length=255, blank=True)
    scan_updated_at = models.DateTimeField(null=True, blank=True)
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
    reserved_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    prepared_quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])

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
    order_line = models.ForeignKey(OrderLine, on_delete=models.CASCADE, related_name="reservations")
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
    scan_status = models.CharField(
        max_length=20,
        choices=DocumentScanStatus.choices,
        default=DocumentScanStatus.CLEAN,
    )
    scan_message = models.CharField(max_length=255, blank=True)
    scan_updated_at = models.DateTimeField(null=True, blank=True)
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


class DestinationCorrespondentDefault(models.Model):
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name="destination_correspondent_defaults",
    )
    correspondent_org = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="destination_correspondent_defaults",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["destination__city", "correspondent_org__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["destination", "correspondent_org"],
                name="wms_destination_corr_default_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.destination} - {self.correspondent_org}"

    def clean(self):
        super().clean()
        errors = {}
        if self.correspondent_org_id:
            from contacts.models import ContactType

            if self.correspondent_org.contact_type != ContactType.ORGANIZATION:
                errors["correspondent_org"] = "Le correspondant doit etre une structure."
            elif self.is_active and not self.correspondent_org.is_active:
                errors["correspondent_org"] = "Le correspondant actif doit etre actif."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class DestinationCorrespondentOverride(models.Model):
    destination = models.ForeignKey(
        Destination,
        on_delete=models.CASCADE,
        related_name="destination_correspondent_overrides",
    )
    correspondent_org = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="destination_correspondent_overrides",
    )
    shipper_org = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="destination_correspondent_overrides_as_shipper",
    )
    recipient_org = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="destination_correspondent_overrides_as_recipient",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "destination__city",
            "correspondent_org__name",
            "shipper_org__name",
            "recipient_org__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["destination", "correspondent_org", "shipper_org", "recipient_org"],
                name="wms_destination_corr_override_unique_key",
            ),
            _check_constraint_compat(
                condition=(
                    models.Q(shipper_org__isnull=False) | models.Q(recipient_org__isnull=False)
                ),
                name="wms_destination_corr_override_requires_scope",
            ),
        ]

    def __str__(self) -> str:
        scope_parts = []
        if self.shipper_org_id:
            scope_parts.append(f"expediteur={self.shipper_org}")
        if self.recipient_org_id:
            scope_parts.append(f"destinataire={self.recipient_org}")
        scope = ", ".join(scope_parts) or "scope manquant"
        return f"{self.destination} - {self.correspondent_org} [{scope}]"

    def clean(self):
        super().clean()
        errors = {}
        from contacts.models import ContactType

        if self.correspondent_org_id:
            if self.correspondent_org.contact_type != ContactType.ORGANIZATION:
                errors["correspondent_org"] = "Le correspondant doit etre une structure."
            elif self.is_active and not self.correspondent_org.is_active:
                errors["correspondent_org"] = "Le correspondant actif doit etre actif."

        if self.shipper_org_id:
            if self.shipper_org.contact_type != ContactType.ORGANIZATION:
                errors["shipper_org"] = "L'expediteur de scope doit etre une structure."
            elif not self.shipper_org.is_active:
                errors["shipper_org"] = "L'expediteur de scope doit etre actif."

        if self.recipient_org_id:
            if self.recipient_org.contact_type != ContactType.ORGANIZATION:
                errors["recipient_org"] = "Le destinataire de scope doit etre une structure."
            elif not self.recipient_org.is_active:
                errors["recipient_org"] = "Le destinataire de scope doit etre actif."

        if not self.shipper_org_id and not self.recipient_org_id:
            errors["__all__"] = "Definir au moins un scope expediteur ou destinataire."

        if errors:
            raise ValidationError(errors)

    def matches(self, *, shipper_org=None, recipient_org=None) -> bool:
        if self.shipper_org_id and (not shipper_org or shipper_org.id != self.shipper_org_id):
            return False
        if self.recipient_org_id and (
            not recipient_org or recipient_org.id != self.recipient_org_id
        ):
            return False
        return True

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
