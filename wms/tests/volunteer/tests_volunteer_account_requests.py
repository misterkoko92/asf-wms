from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from wms.models import (
    IntegrationEvent,
    VolunteerAccountRequest,
    VolunteerAccountRequestStatus,
    VolunteerProfile,
)
from wms.volunteer_account_request_handlers import approve_volunteer_account_request


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
