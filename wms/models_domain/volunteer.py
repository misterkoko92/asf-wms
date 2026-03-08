from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone


class VolunteerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="volunteer_profile",
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="volunteer_profiles",
    )
    volunteer_id = models.PositiveIntegerField(unique=True, blank=True, null=True)
    short_name = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    geo_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geo_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["volunteer_id", "user__last_name", "user__first_name", "id"]

    def __str__(self) -> str:
        name = self.user.get_full_name().strip() if self.user_id else ""
        label = name or self.user.email if self.user_id else ""
        return (
            f"{self.volunteer_id} - {label}"
            if self.volunteer_id and label
            else str(self.volunteer_id or self.pk or "Volunteer")
        )

    def save(self, *args, **kwargs):
        if not self.volunteer_id:
            max_id = (
                self.__class__.objects.aggregate(Max("volunteer_id")).get("volunteer_id__max") or 0
            )
            self.volunteer_id = max_id + 1
        if self.user_id and self.user.first_name and not self.short_name:
            self.short_name = self.user.first_name.strip()[:30]
        super().save(*args, **kwargs)


class VolunteerConstraint(models.Model):
    volunteer = models.OneToOneField(
        VolunteerProfile,
        on_delete=models.CASCADE,
        related_name="constraints",
    )
    max_days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    max_expeditions_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    max_expeditions_per_day = models.PositiveSmallIntegerField(null=True, blank=True)
    max_wait_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["volunteer__volunteer_id", "volunteer_id"]

    def __str__(self) -> str:
        return f"Contraintes benevole {self.volunteer.volunteer_id}"


class VolunteerAvailability(models.Model):
    volunteer = models.ForeignKey(
        VolunteerProfile,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time", "id"]

    def __str__(self) -> str:
        return (
            f"{self.volunteer.volunteer_id} {self.date} "
            f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        )

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({"end_time": "L'heure de fin doit etre apres l'heure de debut."})
        if not self.volunteer_id or not self.date or not self.start_time or not self.end_time:
            return
        overlaps = VolunteerAvailability.objects.filter(
            volunteer=self.volunteer,
            date=self.date,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlaps.exists():
            raise ValidationError("Cette plage horaire chevauche une disponibilite existante.")


class VolunteerUnavailability(models.Model):
    volunteer = models.ForeignKey(
        VolunteerProfile,
        on_delete=models.CASCADE,
        related_name="unavailabilities",
    )
    date = models.DateField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["volunteer", "date"],
                name="unique_volunteer_unavailability_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"Indisponible {self.volunteer.volunteer_id} {self.date}"


class VolunteerAccountRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class VolunteerAccountRequest(models.Model):
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    geo_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geo_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=VolunteerAccountRequestStatus.choices,
        default=VolunteerAccountRequestStatus.PENDING,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_volunteer_account_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email
