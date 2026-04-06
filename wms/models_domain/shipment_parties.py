from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from contacts.models import Contact, ContactType

from .inventory import Destination


class ShipmentValidationStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    VALIDATED = "validated", _("Valide")
    REJECTED = "rejected", _("Refuse")


class RecipientProductPreferenceStatus(models.TextChoices):
    REQUESTED = "requested", _("Demande")
    ALLOWED = "allowed", _("Autorise")
    REFUSED = "refused", _("Refuse")


class RecipientProductPreferencePeriodUnit(models.TextChoices):
    WEEK = "week", _("Semaine")
    MONTH = "month", _("Mois")


class RecipientProductPreferenceSource(models.TextChoices):
    PORTAL = "portal", _("Portail")
    SCAN_ADMIN = "scan_admin", _("Scan admin")
    SYSTEM = "system", _("Systeme")


class ShipmentPreferenceOverrideAction(models.TextChoices):
    OVERRIDE_REFUSAL = "override_refusal", _("Override refusal")


class ShipmentShipper(models.Model):
    organization = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="shipment_shippers",
    )
    default_contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="shipment_shipper_defaults",
    )
    validation_status = models.CharField(
        max_length=20,
        choices=ShipmentValidationStatus.choices,
        default=ShipmentValidationStatus.PENDING,
    )
    can_send_to_all = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["organization__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                name="wms_shipment_shipper_unique_organization",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization}"

    def clean(self):
        super().clean()
        errors = {}
        if self.organization_id:
            if self.organization.contact_type != ContactType.ORGANIZATION:
                errors["organization"] = _("L'expediteur doit etre une structure.")
            elif not self.organization.is_active:
                errors["organization"] = _("L'expediteur doit etre actif.")

        if self.default_contact_id:
            if self.default_contact.contact_type != ContactType.PERSON:
                errors["default_contact"] = _("Le referent expediteur doit etre une personne.")
            elif (
                self.organization_id
                and self.default_contact.organization_id != self.organization_id
            ):
                errors["default_contact"] = _(
                    "Le referent expediteur doit appartenir a la structure expediteur."
                )
            elif not self.default_contact.is_active:
                errors["default_contact"] = _("Le referent expediteur doit etre actif.")
        elif self.is_active:
            errors["default_contact"] = _("Un expediteur actif requiert un referent par defaut.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ShipmentRecipientOrganization(models.Model):
    organization = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="shipment_recipient_organizations",
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.PROTECT,
        related_name="shipment_recipient_organizations",
    )
    validation_status = models.CharField(
        max_length=20,
        choices=ShipmentValidationStatus.choices,
        default=ShipmentValidationStatus.PENDING,
    )
    is_correspondent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["destination__city", "organization__name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "destination"],
                name="wms_shipment_recipient_org_unique_org_destination",
            ),
            models.UniqueConstraint(
                fields=["destination"],
                condition=models.Q(is_correspondent=True, is_active=True),
                name="wms_shipment_recipient_org_single_active_correspondent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization} ({self.destination})"

    def clean(self):
        super().clean()
        errors = {}
        if self.organization_id:
            if self.organization.contact_type != ContactType.ORGANIZATION:
                errors["organization"] = _("Le destinataire doit etre une structure.")
            elif not self.organization.is_active:
                errors["organization"] = _("Le destinataire doit etre actif.")

        if self.destination_id and not self.destination.is_active:
            errors["destination"] = _("La destination doit etre active.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ShipmentRecipientContact(models.Model):
    recipient_organization = models.ForeignKey(
        ShipmentRecipientOrganization,
        on_delete=models.CASCADE,
        related_name="recipient_contacts",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="shipment_recipient_contacts",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["recipient_organization__organization__name", "contact__last_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient_organization", "contact"],
                name="wms_shipment_recipient_contact_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contact} - {self.recipient_organization}"

    def clean(self):
        super().clean()
        errors = {}
        if self.contact_id:
            if self.contact.contact_type != ContactType.PERSON:
                errors["contact"] = _("Le referent destinataire doit etre une personne.")
            elif not self.contact.is_active:
                errors["contact"] = _("Le referent destinataire doit etre actif.")
            elif (
                self.recipient_organization_id
                and self.contact.organization_id != self.recipient_organization.organization_id
            ):
                errors["contact"] = _(
                    "Le referent destinataire doit appartenir a la structure destinataire."
                )
        if self.recipient_organization_id and not self.recipient_organization.is_active:
            errors["recipient_organization"] = _("La structure destinataire doit etre active.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ShipmentShipperRecipientLink(models.Model):
    shipper = models.ForeignKey(
        ShipmentShipper,
        on_delete=models.CASCADE,
        related_name="recipient_links",
    )
    recipient_organization = models.ForeignKey(
        ShipmentRecipientOrganization,
        on_delete=models.CASCADE,
        related_name="shipper_links",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            "shipper__organization__name",
            "recipient_organization__organization__name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["shipper", "recipient_organization"],
                name="wms_shipment_shipper_recipient_link_unique_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.shipper} -> {self.recipient_organization}"

    def clean(self):
        super().clean()
        errors = {}
        if self.shipper_id and not self.shipper.is_active:
            errors["shipper"] = _("L'expediteur doit etre actif.")
        if self.recipient_organization_id and not self.recipient_organization.is_active:
            errors["recipient_organization"] = _("La structure destinataire doit etre active.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ShipmentAuthorizedRecipientContact(models.Model):
    link = models.ForeignKey(
        ShipmentShipperRecipientLink,
        on_delete=models.CASCADE,
        related_name="authorized_recipient_contacts",
    )
    recipient_contact = models.ForeignKey(
        ShipmentRecipientContact,
        on_delete=models.CASCADE,
        related_name="authorized_links",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = [
            "link__shipper__organization__name",
            "-is_default",
            "recipient_contact__contact__last_name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["link", "recipient_contact"],
                name="wms_shipment_authorized_recipient_contact_unique_pair",
            ),
            models.UniqueConstraint(
                fields=["link"],
                condition=models.Q(is_default=True, is_active=True),
                name="wms_shipment_authorized_recipient_contact_single_default",
            ),
        ]

    def __str__(self) -> str:
        suffix = " (defaut)" if self.is_default else ""
        return f"{self.link} - {self.recipient_contact}{suffix}"

    def clean(self):
        super().clean()
        errors = {}
        link = getattr(self, "link", None)
        recipient_contact = getattr(self, "recipient_contact", None)

        if link is not None and not link.is_active:
            errors["link"] = _("Le lien doit etre actif.")

        if recipient_contact is not None:
            if not recipient_contact.is_active:
                errors["recipient_contact"] = _("Le referent destinataire doit etre actif.")
            elif link is not None and (
                recipient_contact.recipient_organization_id != link.recipient_organization_id
            ):
                errors["recipient_contact"] = _(
                    "Le referent destinataire doit appartenir a la structure destinataire liee."
                )
        if self.is_default and link is not None and recipient_contact is not None:
            if not recipient_contact.is_active:
                errors["recipient_contact"] = _(
                    "Le referent destinataire par defaut doit etre actif."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class RecipientProductPreference(models.Model):
    recipient_organization = models.ForeignKey(
        ShipmentRecipientOrganization,
        on_delete=models.CASCADE,
        related_name="product_preferences",
    )
    product = models.ForeignKey(
        "wms.Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recipient_preferences",
    )
    category = models.ForeignKey(
        "wms.ProductCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recipient_preferences",
    )
    status = models.CharField(max_length=20, choices=RecipientProductPreferenceStatus.choices)
    quantity_target = models.PositiveIntegerField(null=True, blank=True)
    period_unit = models.CharField(
        max_length=12,
        choices=RecipientProductPreferencePeriodUnit.choices,
        blank=True,
        default="",
    )
    notes = models.TextField(blank=True)
    source = models.CharField(
        max_length=20,
        choices=RecipientProductPreferenceSource.choices,
        default=RecipientProductPreferenceSource.SYSTEM,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipient_product_preferences_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipient_product_preferences_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["recipient_organization_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient_organization", "product"],
                condition=models.Q(product__isnull=False),
                name="wms_recipient_product_pref_unique_product",
            ),
            models.UniqueConstraint(
                fields=["recipient_organization", "category"],
                condition=models.Q(category__isnull=False),
                name="wms_recipient_product_pref_unique_category",
            ),
        ]

    def __str__(self) -> str:
        target = self.product or self.category
        return f"{self.recipient_organization} - {target} ({self.status})"

    def clean(self):
        super().clean()
        errors = {}
        has_product = self.product_id is not None
        has_category = self.category_id is not None

        if has_product == has_category:
            message = _("Choisissez exactement un produit ou une categorie.")
            errors["product"] = message
            errors["category"] = message

        if self.status in (
            RecipientProductPreferenceStatus.REQUESTED,
            RecipientProductPreferenceStatus.ALLOWED,
        ):
            if not self.quantity_target:
                errors["quantity_target"] = _(
                    "La quantite cible est requise pour une preference demandee ou autorisee."
                )
            if not self.period_unit:
                errors["period_unit"] = _(
                    "La periode est requise pour une preference demandee ou autorisee."
                )
        elif self.status == RecipientProductPreferenceStatus.REFUSED:
            if self.quantity_target is not None:
                errors["quantity_target"] = _(
                    "Une preference refusee ne peut pas porter de quantite cible."
                )
            if self.period_unit:
                errors["period_unit"] = _("Une preference refusee ne peut pas porter de periode.")
            if has_category:
                errors["category"] = _("Le statut refuse n'est pas autorise au niveau categorie.")

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ShipmentPreferenceOverride(models.Model):
    shipment = models.ForeignKey(
        "wms.Shipment",
        on_delete=models.CASCADE,
        related_name="preference_overrides",
    )
    carton = models.ForeignKey(
        "wms.Carton",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preference_overrides",
    )
    recipient_organization = models.ForeignKey(
        ShipmentRecipientOrganization,
        on_delete=models.PROTECT,
        related_name="preference_overrides",
    )
    product = models.ForeignKey(
        "wms.Product",
        on_delete=models.PROTECT,
        related_name="preference_overrides",
    )
    preference_status_snapshot = models.CharField(max_length=20)
    action = models.CharField(
        max_length=24,
        choices=ShipmentPreferenceOverrideAction.choices,
        default=ShipmentPreferenceOverrideAction.OVERRIDE_REFUSAL,
    )
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipment_preference_overrides_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["shipment_id", "id"]

    def __str__(self) -> str:
        return f"{self.shipment} - {self.product} ({self.action})"
