from django.db import models, transaction
from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver


class ContactTag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    asf_prefix = models.CharField(max_length=10, blank=True, null=True, unique=True)
    asf_last_number = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ContactType(models.TextChoices):
    ORGANIZATION = "organization", "Organization"
    PERSON = "person", "Person"


class Contact(models.Model):
    contact_type = models.CharField(
        max_length=20, choices=ContactType.choices, default=ContactType.ORGANIZATION
    )
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=40, blank=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    organization = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
        limit_choices_to={"contact_type": ContactType.ORGANIZATION},
    )
    destination = models.ForeignKey(
        "wms.Destination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacts",
        limit_choices_to={"is_active": True},
        help_text="Laisser vide pour toutes les destinations.",
    )
    destinations = models.ManyToManyField(
        "wms.Destination",
        blank=True,
        related_name="contacts_scoped",
        help_text="Laisser vide pour toutes les destinations.",
    )
    linked_shippers = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="linked_recipients",
        help_text="Utilise pour les destinataires: vide = tous les expéditeurs.",
    )
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    email2 = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    phone2 = models.CharField(max_length=40, blank=True)
    siret = models.CharField(max_length=30, blank=True)
    vat_number = models.CharField(max_length=40, blank=True)
    legal_registration_number = models.CharField(max_length=80, blank=True)
    asf_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    use_organization_address = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    tags = models.ManyToManyField(ContactTag, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_effective_addresses(self):
        if (
            self.contact_type == ContactType.PERSON
            and self.use_organization_address
            and self.organization
        ):
            return self.organization.addresses.all()
        return self.addresses.all()

    def get_effective_address(self):
        addresses = self.get_effective_addresses()
        return addresses.filter(is_default=True).first() or addresses.first()

    def save(self, *args, **kwargs):
        if self.contact_type == ContactType.PERSON and not self.name:
            full_name = " ".join(
                part for part in [self.first_name, self.last_name] if part
            ).strip()
            if full_name:
                self.name = full_name
        super().save(*args, **kwargs)
        if self.contact_type == ContactType.PERSON and self.use_organization_address:
            _sync_contact_address_from_org(self)


class ContactAddress(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=80, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, default="France")
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    is_default = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["contact__name", "city", "address_line1"]

    def __str__(self) -> str:
        label = f"{self.label} - " if self.label else ""
        parts = [self.address_line1]
        if self.city:
            parts.append(self.city)
        return f"{label}{', '.join(parts)}"

    def save(self, *args, **kwargs):
        if self.is_default:
            ContactAddress.objects.filter(contact=self.contact).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)
        if (
            self.contact.contact_type == ContactType.ORGANIZATION
            and self.is_default
        ):
            _sync_people_for_org(self.contact)


def _select_asf_tag(contact):
    return (
        contact.tags.exclude(asf_prefix__isnull=True)
        .exclude(asf_prefix="")
        .order_by("name")
        .first()
    )


def _assign_asf_id(contact):
    if contact.asf_id or contact.contact_type != ContactType.ORGANIZATION:
        return
    tag = _select_asf_tag(contact)
    if not tag:
        return
    with transaction.atomic():
        locked_tag = ContactTag.objects.select_for_update().get(pk=tag.pk)
        locked_tag.asf_last_number += 1
        locked_tag.save(update_fields=["asf_last_number"])
        number = locked_tag.asf_last_number
    contact.asf_id = f"{locked_tag.asf_prefix}-{number:04d}"
    contact.save(update_fields=["asf_id"])


def _sync_contact_address_from_org(contact):
    if not contact.use_organization_address or not contact.organization:
        return
    org_address = (
        contact.organization.addresses.filter(is_default=True).first()
        or contact.organization.addresses.first()
    )
    if not org_address:
        return
    address = contact.addresses.filter(is_default=True).first()
    if not address:
        address = ContactAddress(contact=contact, is_default=True)
    address.address_line1 = org_address.address_line1
    address.address_line2 = org_address.address_line2
    address.postal_code = org_address.postal_code
    address.city = org_address.city
    address.region = org_address.region
    address.country = org_address.country
    address.save()


def _sync_people_for_org(organization):
    for person in organization.members.filter(use_organization_address=True):
        _sync_contact_address_from_org(person)


@receiver(m2m_changed, sender=Contact.tags.through)
def _contact_tags_changed(sender, instance, action, **kwargs):
    if action != "post_add":
        return
    _assign_asf_id(instance)


@receiver(pre_delete, sender=Contact)
def _contact_pre_delete(sender, instance, **kwargs):
    if instance.contact_type != ContactType.ORGANIZATION:
        return
    former_note = f"anciennement : {instance.name}"
    for person in instance.members.all():
        notes = (person.notes or "").strip()
        if former_note not in notes:
            notes = f"{notes}\n{former_note}".strip() if notes else former_note
        person.notes = notes
        person.organization = None
        person.use_organization_address = False
        person.save(update_fields=["notes", "organization", "use_organization_address"])

# Create your models here.
