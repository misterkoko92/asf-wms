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


class VolunteerAvailabilityViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="availability@example.com",
            email="availability@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.profile = VolunteerProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def _week_payload(self):
        payload = {
            "week_start": "2026-03-09",
            "form-TOTAL_FORMS": "7",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }
        dates = [
            "2026-03-09",
            "2026-03-10",
            "2026-03-11",
            "2026-03-12",
            "2026-03-13",
            "2026-03-14",
            "2026-03-15",
        ]
        for index, date_value in enumerate(dates):
            payload[f"form-{index}-date"] = date_value
            payload[f"form-{index}-availability"] = "unavailable"
            payload[f"form-{index}-start_time"] = ""
            payload[f"form-{index}-end_time"] = ""
        payload["form-0-availability"] = "available"
        payload["form-0-start_time"] = "09:00"
        payload["form-0-end_time"] = "12:00"
        return payload

    def test_availability_list_renders_existing_entries(self):
        VolunteerAvailability.objects.create(
            volunteer=self.profile,
            date="2026-03-09",
            start_time="09:00",
            end_time="12:00",
        )

        response = self.client.get(reverse("volunteer:availability_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "09:00")

    def test_create_weekly_availability_redirects_to_list(self):
        response = self.client.post(
            reverse("volunteer:availability_create"),
            self._week_payload(),
        )

        self.assertRedirects(response, reverse("volunteer:availability_list"))
        availability = VolunteerAvailability.objects.get(volunteer=self.profile)
        self.assertEqual(str(availability.start_time), "09:00:00")
        self.assertEqual(str(availability.end_time), "12:00:00")

    def test_update_availability_persists_changes(self):
        availability = VolunteerAvailability.objects.create(
            volunteer=self.profile,
            date="2026-03-09",
            start_time="09:00",
            end_time="12:00",
        )

        response = self.client.post(
            reverse("volunteer:availability_edit", args=[availability.pk]),
            {
                "date": "2026-03-09",
                "start_time": "10:00",
                "end_time": "13:00",
            },
        )

        self.assertRedirects(response, reverse("volunteer:availability_list"))
        availability.refresh_from_db()
        self.assertEqual(str(availability.start_time), "10:00:00")
        self.assertEqual(str(availability.end_time), "13:00:00")

    def test_delete_availability_removes_entry(self):
        availability = VolunteerAvailability.objects.create(
            volunteer=self.profile,
            date="2026-03-09",
            start_time="09:00",
            end_time="12:00",
        )

        response = self.client.post(
            reverse("volunteer:availability_delete", args=[availability.pk])
        )

        self.assertRedirects(response, reverse("volunteer:availability_list"))
        self.assertFalse(VolunteerAvailability.objects.filter(pk=availability.pk).exists())

    def test_recap_renders_week_rows(self):
        VolunteerAvailability.objects.create(
            volunteer=self.profile,
            date="2026-03-09",
            start_time="09:00",
            end_time="12:00",
        )

        response = self.client.get(
            reverse("volunteer:availability_recap"),
            {"week": "11", "year": "2026"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semaine")
        self.assertContains(response, self.user.email)
