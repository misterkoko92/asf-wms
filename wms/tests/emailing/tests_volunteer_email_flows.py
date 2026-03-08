from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from wms.models import IntegrationEvent, VolunteerProfile
from wms.volunteer_access import build_volunteer_urls, send_volunteer_access_email


class VolunteerAccessEmailFlowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

    def test_build_volunteer_urls_returns_login_and_set_password_links(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )
        VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = self.factory.get("/admin/")
        request.user = self.admin_user

        login_url, set_password_url = build_volunteer_urls(request=request, user=user)

        self.assertIn("/benevole/login/", login_url)
        self.assertIn("/benevole/set-password/", set_password_url)

    def test_send_volunteer_access_email_enqueues_email_with_links(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )
        VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = self.factory.get("/admin/")
        request.user = self.admin_user

        queued = send_volunteer_access_email(request=request, user=user)

        self.assertTrue(queued)
        event = IntegrationEvent.objects.get()
        self.assertEqual(event.payload["recipient"], ["access@example.com"])
        self.assertIn("/benevole/login/", event.payload["message"])
        self.assertIn("/benevole/set-password/", event.payload["message"])
