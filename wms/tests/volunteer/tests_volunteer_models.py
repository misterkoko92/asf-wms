from datetime import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from wms.models import VolunteerAvailability, VolunteerProfile, VolunteerUnavailability


class VolunteerModelTests(TestCase):
    def test_volunteer_profile_assigns_next_volunteer_id(self):
        user = get_user_model().objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

        profile = VolunteerProfile.objects.create(user=user)

        self.assertEqual(profile.volunteer_id, 1)

    def test_availability_rejects_overlaps(self):
        user = get_user_model().objects.create_user(
            username="overlap@example.com",
            email="overlap@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        VolunteerAvailability.objects.create(
            volunteer=profile,
            date="2026-03-09",
            start_time=time(9, 0),
            end_time=time(11, 0),
        )

        overlapping = VolunteerAvailability(
            volunteer=profile,
            date="2026-03-09",
            start_time=time(10, 0),
            end_time=time(12, 0),
        )

        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_unavailability_is_unique_per_day(self):
        user = get_user_model().objects.create_user(
            username="unique@example.com",
            email="unique@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user)
        VolunteerUnavailability.objects.create(volunteer=profile, date="2026-03-10")

        with self.assertRaises(IntegrityError):
            VolunteerUnavailability.objects.create(volunteer=profile, date="2026-03-10")
