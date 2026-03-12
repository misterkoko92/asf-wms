from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from wms.models import (
    IntegrationEvent,
    VolunteerAccountRequest,
    VolunteerAccountRequestStatus,
    VolunteerProfile,
)
from wms.volunteer_account_request_handlers import (
    approve_volunteer_account_request,
    describe_volunteer_account_request_skip_reason,
)


class VolunteerAccountRequestTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )

    def _request(self):
        request = self.factory.post("/admin/")
        request.user = self.admin_user
        return request

    def test_approving_request_creates_user_and_profile(self):
        account_request = VolunteerAccountRequest.objects.create(
            first_name="Lou",
            last_name="Durand",
            email="lou@example.com",
            phone="+33601020304",
            address_line1="10 rue Test",
            postal_code="75001",
            city="Paris",
            country="France",
            status=VolunteerAccountRequestStatus.PENDING,
        )

        ok, reason = approve_volunteer_account_request(
            request=self._request(),
            account_request=account_request,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        account_request.refresh_from_db()
        self.assertEqual(account_request.status, VolunteerAccountRequestStatus.APPROVED)
        self.assertEqual(account_request.reviewed_by, self.admin_user)
        profile = VolunteerProfile.objects.get(user__email="lou@example.com")
        self.assertEqual(profile.phone, "+33601020304")
        self.assertEqual(profile.city, "Paris")
        self.assertTrue(profile.must_change_password)
        self.assertEqual(IntegrationEvent.objects.count(), 1)

    def test_approving_request_rejects_reserved_staff_email(self):
        get_user_model().objects.create_user(
            username="staff-existing",
            email="staff@example.com",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        account_request = VolunteerAccountRequest.objects.create(
            first_name="Lou",
            email="staff@example.com",
            status=VolunteerAccountRequestStatus.PENDING,
        )

        ok, reason = approve_volunteer_account_request(
            request=self._request(),
            account_request=account_request,
        )

        self.assertFalse(ok)
        self.assertEqual(reason, "email reserve")
        self.assertFalse(VolunteerProfile.objects.filter(user__email="staff@example.com").exists())

    @override_settings(EMAIL_DELIVERY_MODE="direct_only")
    @mock.patch("wms.emailing.send_email_safe", return_value=True)
    def test_approving_request_sends_directly_in_direct_only_mode(self, send_email_mock):
        account_request = VolunteerAccountRequest.objects.create(
            first_name="Lou",
            last_name="Durand",
            email="lou@example.com",
            status=VolunteerAccountRequestStatus.PENDING,
        )

        ok, reason = approve_volunteer_account_request(
            request=self._request(),
            account_request=account_request,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        self.assertEqual(IntegrationEvent.objects.count(), 0)
        send_email_mock.assert_called_once()

    def test_describe_skip_reason_returns_passthrough_for_unknown_reason(self):
        self.assertEqual(describe_volunteer_account_request_skip_reason("custom"), "custom")

    def test_approving_request_updates_existing_non_staff_user_and_profile(self):
        user = get_user_model().objects.create_user(
            username="old-username",
            email="lou@example.com",
            password="pass1234",  # pragma: allowlist secret
            first_name="Old",
            last_name="Name",
            is_active=False,
        )
        profile = VolunteerProfile.objects.create(
            user=user,
            phone="0000",
            address_line1="Old address",
            postal_code="99999",
            city="Old city",
            country="Belgique",
            short_name="Old short",
            is_active=False,
            must_change_password=False,
        )
        account_request = VolunteerAccountRequest.objects.create(
            first_name="Lou",
            last_name="Durand",
            email="lou@example.com",
            phone="+33601020304",
            address_line1="10 rue Test",
            postal_code="75001",
            city="Paris",
            country="France",
            status=VolunteerAccountRequestStatus.PENDING,
        )

        ok, reason = approve_volunteer_account_request(
            request=self._request(),
            account_request=account_request,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        user.refresh_from_db()
        profile.refresh_from_db()
        account_request.refresh_from_db()
        self.assertEqual(user.pk, profile.user_id)
        self.assertEqual(user.username, "lou@example.com")
        self.assertEqual(user.first_name, "Lou")
        self.assertEqual(user.last_name, "Durand")
        self.assertTrue(user.is_active)
        self.assertEqual(profile.phone, "+33601020304")
        self.assertEqual(profile.city, "Paris")
        self.assertEqual(profile.short_name, "Lou")
        self.assertTrue(profile.is_active)
        self.assertTrue(profile.must_change_password)
        self.assertEqual(account_request.status, VolunteerAccountRequestStatus.APPROVED)
        self.assertEqual(IntegrationEvent.objects.count(), 1)

    def test_approving_request_without_first_name_keeps_existing_short_name(self):
        user = get_user_model().objects.create_user(
            username="lou@example.com",
            email="lou@example.com",
            password="pass1234",  # pragma: allowlist secret
            first_name="Legacy",
            last_name="Name",
        )
        profile = VolunteerProfile.objects.create(
            user=user,
            short_name="Legacy short",
            is_active=False,
            must_change_password=False,
        )
        account_request = VolunteerAccountRequest.objects.create(
            first_name="",
            last_name="Durand",
            email="lou@example.com",
            status=VolunteerAccountRequestStatus.PENDING,
        )

        ok, reason = approve_volunteer_account_request(
            request=self._request(),
            account_request=account_request,
        )

        self.assertTrue(ok)
        self.assertEqual(reason, "")
        profile.refresh_from_db()
        self.assertEqual(profile.short_name, "Legacy short")
