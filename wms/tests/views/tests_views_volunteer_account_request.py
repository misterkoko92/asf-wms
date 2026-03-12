from unittest import mock

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from wms import views_volunteer_account_request
from wms.models import VolunteerAccountRequest, VolunteerAccountRequestStatus
from wms.views_volunteer_account_request import REQUEST_THROTTLE_SECONDS_DEFAULT


class VolunteerAccountRequestViewTests(TestCase):
    def test_public_request_creates_pending_request(self):
        response = self.client.post(
            reverse("volunteer:request_account"),
            {
                "first_name": "Lou",
                "last_name": "Durand",
                "email": "lou@example.com",
                "phone": "+33601020304",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )

        self.assertRedirects(response, reverse("volunteer:request_account_done"))
        account_request = VolunteerAccountRequest.objects.get()
        self.assertEqual(account_request.status, VolunteerAccountRequestStatus.PENDING)
        self.assertEqual(account_request.first_name, "Lou")
        self.assertEqual(account_request.city, "Paris")

    def test_request_account_done_page_renders(self):
        response = self.client.get(reverse("volunteer:request_account_done"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demande envoyee")

    @mock.patch("wms.views_volunteer_account_request._reserve_throttle_slot", return_value=False)
    def test_public_request_shows_error_when_throttled(self, _reserve_mock):
        response = self.client.post(
            reverse("volunteer:request_account"),
            {
                "first_name": "Lou",
                "last_name": "Durand",
                "email": "lou@example.com",
                "phone": "+33601020304",
                "address_line1": "10 rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "France",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Une demande recente a deja ete envoyee")
        self.assertEqual(VolunteerAccountRequest.objects.count(), 0)

    @mock.patch("wms.views_volunteer_account_request._release_throttle_slot")
    @mock.patch("wms.views_volunteer_account_request._reserve_throttle_slot", return_value=True)
    def test_public_request_releases_throttle_slot_when_save_fails(
        self,
        _reserve_mock,
        release_mock,
    ):
        payload = {
            "first_name": "Lou",
            "last_name": "Durand",
            "email": "lou@example.com",
            "phone": "+33601020304",
            "address_line1": "10 rue Test",
            "postal_code": "75001",
            "city": "Paris",
            "country": "France",
        }

        with mock.patch(
            "wms.models.VolunteerAccountRequest.save", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("volunteer:request_account"), payload)

        release_mock.assert_called_once_with(email="lou@example.com", client_ip="127.0.0.1")


class VolunteerAccountRequestHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS="invalid")
    def test_get_throttle_seconds_invalid_value_falls_back_to_default(self):
        self.assertEqual(
            views_volunteer_account_request._get_throttle_seconds(),
            REQUEST_THROTTLE_SECONDS_DEFAULT,
        )

    @override_settings(VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_reserve_throttle_slot_releases_email_key_on_partial_ip_failure(self):
        with mock.patch.object(
            views_volunteer_account_request.cache,
            "add",
            side_effect=[True, False],
        ):
            with mock.patch.object(views_volunteer_account_request.cache, "delete") as delete_mock:
                reserved = views_volunteer_account_request._reserve_throttle_slot(
                    email="lou@example.com",
                    client_ip="10.0.0.1",
                )

        self.assertFalse(reserved)
        delete_mock.assert_called_once_with("volunteer-account-request:email:lou@example.com")

    @override_settings(VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_reserve_throttle_slot_releases_ip_key_on_partial_email_failure(self):
        with mock.patch.object(
            views_volunteer_account_request.cache,
            "add",
            side_effect=[False, True],
        ):
            with mock.patch.object(views_volunteer_account_request.cache, "delete") as delete_mock:
                reserved = views_volunteer_account_request._reserve_throttle_slot(
                    email="lou@example.com",
                    client_ip="10.0.0.1",
                )

        self.assertFalse(reserved)
        delete_mock.assert_called_once_with("volunteer-account-request:ip:10.0.0.1")

    @override_settings(VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    def test_release_throttle_slot_is_noop_when_disabled(self):
        with mock.patch.object(
            views_volunteer_account_request.cache,
            "delete_many",
        ) as delete_many_mock:
            views_volunteer_account_request._release_throttle_slot(
                email="lou@example.com",
                client_ip="10.0.0.1",
            )

        delete_many_mock.assert_not_called()

    @override_settings(VOLUNTEER_ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_release_throttle_slot_deletes_email_and_ip_keys(self):
        with mock.patch.object(
            views_volunteer_account_request.cache,
            "delete_many",
        ) as delete_many_mock:
            views_volunteer_account_request._release_throttle_slot(
                email="lou@example.com",
                client_ip="10.0.0.1",
            )

        delete_many_mock.assert_called_once_with(
            [
                "volunteer-account-request:email:lou@example.com",
                "volunteer-account-request:ip:10.0.0.1",
            ]
        )

    @mock.patch("wms.views_volunteer_account_request.get_admin_emails", return_value=[])
    def test_notify_admins_of_request_returns_false_without_recipients(
        self, _get_admin_emails_mock
    ):
        request = self.factory.get("/benevole/request-account/")

        notified = views_volunteer_account_request._notify_admins_of_request(
            request=request,
            account_request=VolunteerAccountRequest(email="lou@example.com"),
        )

        self.assertFalse(notified)

    @mock.patch("wms.views_volunteer_account_request.enqueue_email_safe", return_value=True)
    @mock.patch(
        "wms.views_volunteer_account_request.get_admin_emails", return_value=["admin@example.com"]
    )
    def test_notify_admins_of_request_enqueues_email(self, _get_admin_emails_mock, enqueue_mock):
        request = self.factory.get("/benevole/request-account/")
        request.build_absolute_uri = mock.Mock(
            side_effect=lambda path="": f"https://example.test{path}"
        )

        account_request = VolunteerAccountRequest(
            first_name="Lou",
            last_name="Durand",
            email="lou@example.com",
        )

        notified = views_volunteer_account_request._notify_admins_of_request(
            request=request,
            account_request=account_request,
        )

        self.assertTrue(notified)
        enqueue_mock.assert_called_once()
        _, kwargs = enqueue_mock.call_args
        self.assertEqual(kwargs["recipient"], ["admin@example.com"])
        self.assertIn("lou@example.com", kwargs["message"])

    def test_get_request_view_prefills_france(self):
        response = self.client.get(reverse("volunteer:request_account"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].fields["country"].initial, "France")
