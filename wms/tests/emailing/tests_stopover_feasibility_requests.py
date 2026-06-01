from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from wms.stopover_request_handlers import submit_stopover_feasibility_request


@override_settings(ACCOUNT_REQUEST_VALIDATION_GROUP_NAME="Account_User_Validation")
class StopoverFeasibilityRequestEmailTests(TestCase):
    def _valid_payload(self):
        return {
            "requester_type": "shipper",
            "requested_stopovers": "Bangui",
            "structure_name": "Association Expediteur",
            "legal_form": "association",
            "beneficiary_count": "45",
            "contact_title": "mr",
            "contact_last_name": "MARTIN",
            "contact_first_name": "Louis",
            "contact_email": "louis@example.org",
            "contact_phone": "+33111111111",
            "address_line1": "2 Rue Logistique",
            "address_line2": "",
            "postal_code": "75002",
            "city": "Paris",
            "country": "France",
            "message": "",
        }

    @mock.patch("wms.stopover_request_handlers.send_or_enqueue_email_safe", return_value=True)
    def test_valid_request_sends_internal_email_after_commit(self, send_mock):
        User = get_user_model()
        User.objects.create_user(
            username="admin-stopover",
            email="admin-stopover@example.org",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            is_superuser=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            submit_stopover_feasibility_request(
                self._valid_payload(),
                source="portal_recipient_create",
            )

        send_mock.assert_called_once()
        call_kwargs = send_mock.call_args.kwargs
        self.assertEqual(call_kwargs["subject"], "Demande nouvelle escale")
        self.assertEqual(call_kwargs["recipient"], ["admin-stopover@example.org"])
        self.assertIn("Bangui", call_kwargs["message"])
        self.assertIn("Association Expediteur", call_kwargs["message"])
