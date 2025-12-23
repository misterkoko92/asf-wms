from django.db import models


class ContactTag(models.Model):
    name = models.CharField(max_length=80, unique=True)

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
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    tags = models.ManyToManyField(ContactTag, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


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

# Create your models here.
