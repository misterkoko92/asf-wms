from unittest import mock

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from wms.admin import VolunteerProfileAdmin
from wms.models import (
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    VolunteerUnavailability,
)


class VolunteerAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.superuser = get_user_model().objects.create_superuser(
            "admin",
            "admin@example.com",
            "pass1234",  # pragma: allowlist secret
        )

    def _request(self):
        request = self.factory.post("/admin/")
        request.user = self.superuser
        return request

    def test_volunteer_models_are_registered(self):
        self.assertIn(VolunteerProfile, admin.site._registry)
        self.assertIn(VolunteerConstraint, admin.site._registry)
        self.assertIn(VolunteerAvailability, admin.site._registry)
        self.assertIn(VolunteerUnavailability, admin.site._registry)

    def test_mark_password_change_required_sets_flag(self):
        user = get_user_model().objects.create_user(
            username="benevole@example.com",
            email="benevole@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user, must_change_password=False)
        admin_obj = VolunteerProfileAdmin(VolunteerProfile, self.site)

        with mock.patch.object(admin_obj, "message_user") as message_user_mock:
            admin_obj.mark_password_change_required(
                self._request(),
                VolunteerProfile.objects.filter(pk=profile.pk),
            )

        profile.refresh_from_db()
        self.assertTrue(profile.must_change_password)
        message_user_mock.assert_called_once()

    def test_send_access_email_marks_password_change_and_enqueues_message(self):
        user = get_user_model().objects.create_user(
            username="access@example.com",
            email="access@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        profile = VolunteerProfile.objects.create(user=user, must_change_password=False)
        admin_obj = VolunteerProfileAdmin(VolunteerProfile, self.site)

        with (
            mock.patch("wms.admin.send_volunteer_access_email") as send_access_mock,
            mock.patch.object(admin_obj, "message_user") as message_user_mock,
        ):
            admin_obj.send_access_email(
                self._request(),
                VolunteerProfile.objects.filter(pk=profile.pk),
            )

        profile.refresh_from_db()
        self.assertTrue(profile.must_change_password)
        send_access_mock.assert_called_once()
        message_user_mock.assert_called_once()
