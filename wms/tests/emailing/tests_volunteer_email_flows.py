from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from wms.models import IntegrationEvent, VolunteerProfile
from wms.volunteer_access import (
    build_volunteer_urls,
    build_volunteer_urls_from_base_url,
    send_volunteer_access_email,
)


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

    def test_build_volunteer_urls_from_base_url_returns_relative_paths_when_base_is_missing(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )

        login_url, set_password_url, has_absolute_base_url = build_volunteer_urls_from_base_url(
            site_base_url=" ",
            user=user,
        )

        self.assertEqual(login_url, reverse("volunteer:login"))
        self.assertIn("/benevole/set-password/", set_password_url)
        self.assertFalse(has_absolute_base_url)

    def test_build_volunteer_urls_from_base_url_trims_trailing_slash(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )

        login_url, set_password_url, has_absolute_base_url = build_volunteer_urls_from_base_url(
            site_base_url="https://example.test/root/",
            user=user,
        )

        self.assertEqual(login_url, "https://example.test/root/benevole/login/")
        self.assertIn("https://example.test/root/benevole/set-password/", set_password_url)
        self.assertTrue(has_absolute_base_url)

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

    @override_settings(EMAIL_DELIVERY_MODE="direct_only")
    @mock.patch("wms.emailing.send_email_safe", return_value=True)
    def test_send_volunteer_access_email_sends_directly_in_direct_only_mode(
        self,
        send_email_mock,
    ):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
        )
        VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = self.factory.get("/admin/")
        request.user = self.admin_user

        queued = send_volunteer_access_email(request=request, user=user)

        self.assertTrue(queued)
        self.assertEqual(IntegrationEvent.objects.count(), 0)
        send_email_mock.assert_called_once()

    def test_send_volunteer_access_email_returns_false_when_recipient_is_missing(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="",
        )
        VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        enqueue_mock = mock.Mock(return_value=True)

        queued = send_volunteer_access_email(
            request=request,
            user=user,
            enqueue_email=enqueue_mock,
        )

        self.assertFalse(queued)
        enqueue_mock.assert_not_called()

    def test_send_volunteer_access_email_uses_explicit_email_override(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="",
        )
        VolunteerProfile.objects.create(user=user, must_change_password=True)
        request = self.factory.get("/admin/")
        request.user = self.admin_user
        enqueue_mock = mock.Mock(return_value=True)
        url_builder = mock.Mock(
            return_value=(
                "https://example.test/benevole/login/",
                "https://example.test/benevole/set-password/token/",
            )
        )

        queued = send_volunteer_access_email(
            request=request,
            user=user,
            email="alternate@example.com",
            enqueue_email=enqueue_mock,
            url_builder=url_builder,
        )

        self.assertTrue(queued)
        url_builder.assert_called_once_with(request=request, user=user)
        enqueue_mock.assert_called_once()
        _, kwargs = enqueue_mock.call_args
        self.assertEqual(kwargs["recipient"], ["alternate@example.com"])
        self.assertIn("alternate@example.com", kwargs["message"])
