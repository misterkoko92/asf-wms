from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms import account_request_handlers
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
)


class AccountRequestHelpersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_handles_empty_forwarded_token(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR=" , 203.0.113.9")
        self.assertEqual(account_request_handlers._get_client_ip(request), "unknown")

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS="invalid")
    def test_get_account_request_throttle_seconds_invalid_value_falls_back_to_default(self):
        self.assertEqual(
            account_request_handlers._get_account_request_throttle_seconds(),
            account_request_handlers.ACCOUNT_REQUEST_THROTTLE_SECONDS_DEFAULT,
        )

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    def test_reserve_throttle_slot_returns_true_when_throttling_disabled(self):
        with mock.patch.object(account_request_handlers.cache, "add") as add_mock:
            reserved = account_request_handlers._reserve_throttle_slot(
                email="association@example.com",
                client_ip="10.0.0.1",
            )
        self.assertTrue(reserved)
        add_mock.assert_not_called()

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_reserve_throttle_slot_releases_ip_key_on_partial_failure(self):
        with mock.patch.object(
            account_request_handlers.cache,
            "add",
            side_effect=[False, True],
        ):
            with mock.patch.object(account_request_handlers.cache, "delete") as delete_mock:
                reserved = account_request_handlers._reserve_throttle_slot(
                    email="association@example.com",
                    client_ip="10.0.0.1",
                )

        self.assertFalse(reserved)
        delete_mock.assert_called_once_with("account-request:ip:10.0.0.1")

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    def test_release_throttle_slot_is_noop_when_disabled(self):
        with mock.patch.object(account_request_handlers.cache, "delete") as delete_mock:
            account_request_handlers._release_throttle_slot(
                email="association@example.com",
                client_ip="10.0.0.1",
            )
        delete_mock.assert_not_called()

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_release_throttle_slot_deletes_email_and_ip_keys(self):
        with mock.patch.object(account_request_handlers.cache, "delete") as delete_mock:
            account_request_handlers._release_throttle_slot(
                email="association@example.com",
                client_ip="10.0.0.1",
            )

        self.assertEqual(delete_mock.call_count, 2)
        delete_mock.assert_any_call("account-request:email:association@example.com")
        delete_mock.assert_any_call("account-request:ip:10.0.0.1")

    def test_queue_account_request_emails_logs_when_queueing_fails(self):
        with mock.patch(
            "wms.account_request_handlers.get_admin_emails",
            return_value=["admin@example.com"],
        ):
            with mock.patch(
                "wms.account_request_handlers.enqueue_email_safe",
                side_effect=[False, False],
            ):
                with mock.patch.object(account_request_handlers.LOGGER, "warning") as warning_mock:
                    with self.captureOnCommitCallbacks(execute=True):
                        account_request_handlers._queue_account_request_emails(
                            account_type=PublicAccountRequestType.ASSOCIATION,
                            association_name="Association Test",
                            email="association@example.com",
                            phone="0102030405",
                            requested_username="",
                            admin_url="https://example.com/admin",
                        )

        self.assertEqual(warning_mock.call_count, 2)


class AccountRequestFormHandlerTests(TestCase):
    def setUp(self):
        self.url = reverse("portal:portal_account_request")

    def _payload(self, **overrides):
        payload = {
            "account_type": PublicAccountRequestType.ASSOCIATION.value,
            "association_name": "Association Test",
            "email": "association@example.com",
            "phone": "0102030405",
            "line1": "1 Rue Test",
            "line2": "",
            "postal_code": "75001",
            "city": "Paris",
            "country": "France",
            "notes": "Demande de test",
            "contact_id": "",
        }
        payload.update(overrides)
        return payload

    def _user_payload(self, **overrides):
        payload = {
            "account_type": PublicAccountRequestType.USER.value,
            "requested_username": "wms-user",
            "email": "user@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        payload.update(overrides)
        return payload

    def test_form_validates_required_fields(self):
        response = self.client.post(
            self.url,
            self._payload(association_name="", email="", line1=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Nom de l'association requis.", response.context["errors"])
        self.assertIn("Email requis.", response.context["errors"])
        self.assertIn("Adresse requise.", response.context["errors"])

    def test_form_rejects_existing_pending_request_for_same_email(self):
        PublicAccountRequest.objects.create(
            association_name="Association Existing",
            email="association@example.com",
            address_line1="1 Rue Existing",
            status=PublicAccountRequestStatus.PENDING,
        )

        response = self.client.post(self.url, self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Une demande est déjà en attente pour cet email.")

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    @mock.patch("wms.account_request_handlers.get_admin_emails", return_value=[])
    def test_form_uses_contact_id_and_creates_document(self, _get_admin_emails_mock):
        contact = Contact.objects.create(
            name="Association Contact",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        payload = self._payload(contact_id=str(contact.id))
        payload["doc_statutes"] = SimpleUploadedFile(
            "statutes.pdf",
            b"%PDF-1.4 sample",
            content_type="application/pdf",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 302)
        request_obj = PublicAccountRequest.objects.get(email="association@example.com")
        self.assertEqual(request_obj.contact_id, contact.id)
        self.assertEqual(AccountDocument.objects.count(), 1)
        document = AccountDocument.objects.get()
        self.assertEqual(document.doc_type, AccountDocumentType.STATUTES)

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    def test_form_validates_main_and_other_uploads(self):
        payload = self._payload()
        payload["doc_statutes"] = SimpleUploadedFile(
            "invalid.txt",
            b"plain text",
            content_type="text/plain",
        )
        payload["doc_other"] = [
            SimpleUploadedFile("valid.pdf", b"%PDF-1.4 ok", content_type="application/pdf"),
            SimpleUploadedFile("invalid.exe", b"MZ", content_type="application/octet-stream"),
        ]

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Format non autorise: invalid.txt")
        self.assertContains(response, "Format non autorise: invalid.exe")
        self.assertEqual(PublicAccountRequest.objects.count(), 0)

    def test_form_ignorés_empty_other_upload_entries(self):
        request = RequestFactory().post(
            self.url,
            self._payload(association_name="", email="", line1=""),
        )
        with mock.patch.object(request.FILES, "getlist", return_value=[None]), mock.patch(
            "wms.account_request_handlers.validate_upload"
        ) as validate_mock:
            response = account_request_handlers.handle_account_request_form(
                request,
                redirect_url=self.url,
            )

        self.assertEqual(response.status_code, 200)
        validate_mock.assert_not_called()

    def test_user_form_validates_username_and_password_fields(self):
        response = self.client.post(
            self.url,
            self._user_payload(requested_username="", password1="", password2=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Nom d'utilisateur requis.", response.context["errors"])
        self.assertIn("Mot de passe requis.", response.context["errors"])
        self.assertIn(
            "Confirmation du mot de passe requise.",
            response.context["errors"],
        )

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=0)
    @mock.patch("wms.account_request_handlers.get_admin_emails", return_value=[])
    def test_user_form_creates_request_and_stores_password_hash(self, _get_admin_emails_mock):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, self._user_payload())

        self.assertEqual(response.status_code, 302)
        request_obj = PublicAccountRequest.objects.get(email="user@example.com")
        self.assertEqual(request_obj.account_type, PublicAccountRequestType.USER)
        self.assertEqual(request_obj.requested_username, "wms-user")
        self.assertTrue(request_obj.requested_password_hash)
        self.assertTrue(check_password("StrongPass123!", request_obj.requested_password_hash))
        self.assertEqual(AccountDocument.objects.count(), 0)

    def test_user_form_rejects_pending_request_for_same_username(self):
        PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.USER,
            association_name="wms-user",
            requested_username="wms-user",
            email="other@example.com",
            status=PublicAccountRequestStatus.PENDING,
        )
        response = self.client.post(self.url, self._user_payload())

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Une demande est déjà en attente pour ce nom d'utilisateur.",
            response.context["errors"],
        )

    @override_settings(ACCOUNT_REQUEST_THROTTLE_SECONDS=300)
    def test_form_releases_throttle_slot_when_request_creation_fails(self):
        with mock.patch(
            "wms.account_request_handlers._reserve_throttle_slot",
            return_value=True,
        ):
            with mock.patch(
                "wms.account_request_handlers.PublicAccountRequest.objects.create",
                side_effect=RuntimeError("boom"),
            ):
                with mock.patch(
                    "wms.account_request_handlers._release_throttle_slot"
                ) as release_mock:
                    with self.assertRaisesMessage(RuntimeError, "boom"):
                        self.client.post(self.url, self._payload(), REMOTE_ADDR="10.0.0.9")

        release_mock.assert_called_once_with(
            email="association@example.com",
            client_ip="10.0.0.9",
        )
