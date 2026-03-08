from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerAvailability, VolunteerConstraint, VolunteerProfile


class VolunteerAuthViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="benevole@example.com",
            email="benevole@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.profile = VolunteerProfile.objects.create(
            user=self.user,
            must_change_password=False,
        )

    def test_login_accepts_email_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("volunteer:login"),
            {
                "identifier": "benevole@example.com",
                "password": "pass1234",  # pragma: allowlist secret
            },
        )

        self.assertRedirects(response, reverse("volunteer:dashboard"))

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("volunteer:dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('volunteer:login')}?next={reverse('volunteer:dashboard')}",
        )

    def test_login_redirects_to_change_password_when_required(self):
        self.profile.must_change_password = True
        self.profile.save(update_fields=["must_change_password"])

        response = self.client.post(
            reverse("volunteer:login"),
            {
                "identifier": "benevole@example.com",
                "password": "pass1234",  # pragma: allowlist secret
            },
        )

        self.assertRedirects(response, reverse("volunteer:change_password"))


class VolunteerProfileViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="profile@example.com",
            email="profile@example.com",
            password="pass1234",  # pragma: allowlist secret
            first_name="Jean",
            last_name="Dupont",
        )
        self.profile = VolunteerProfile.objects.create(
            user=self.user,
            phone="+33601020304",
        )
        self.client.force_login(self.user)

    def test_dashboard_renders_recent_availabilities(self):
        VolunteerAvailability.objects.create(
            volunteer=self.profile,
            date="2026-03-09",
            start_time="09:00",
            end_time="12:00",
        )

        response = self.client.get(reverse("volunteer:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tableau de bord")
        self.assertContains(response, "09:00")

    def test_profile_update_persists_changes(self):
        response = self.client.post(
            reverse("volunteer:profile"),
            {
                "email": "profile@example.com",
                "first_name": "Luc",
                "last_name": "Martin",
                "phone": "+33611223344",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )

        self.assertRedirects(response, reverse("volunteer:profile"))
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Luc")
        self.assertEqual(self.user.last_name, "Martin")
        self.assertEqual(self.profile.phone, "+33611223344")
        self.assertEqual(self.profile.address_line1, "10 rue Test")
        self.assertEqual(self.profile.city, "Paris")

    def test_constraints_view_creates_and_updates_constraints(self):
        response = self.client.post(
            reverse("volunteer:constraints"),
            {
                "max_days_per_week": 2,
                "max_expeditions_per_week": 3,
                "max_expeditions_per_day": 1,
                "max_wait_hours": 4,
            },
        )

        self.assertRedirects(response, reverse("volunteer:constraints"))
        constraints = VolunteerConstraint.objects.get(volunteer=self.profile)
        self.assertEqual(constraints.max_days_per_week, 2)
        self.assertEqual(constraints.max_expeditions_per_week, 3)
        self.assertEqual(constraints.max_expeditions_per_day, 1)
        self.assertEqual(constraints.max_wait_hours, 4)
