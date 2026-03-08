from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerProfile


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
