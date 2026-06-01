from django.core.exceptions import ValidationError
from django.test import TestCase

from wms.models import (
    AssociationRecipient,
    PortalAccessGrant,
    PublicAccountRequest,
    ShipmentRecipientOrganization,
    StopoverFeasibilityRequest,
)
from wms.stopover_request_handlers import submit_stopover_feasibility_request


class StopoverFeasibilityRequestTests(TestCase):
    def _valid_payload(self):
        return {
            "requester_type": "recipient",
            "requested_stopovers": "Kisangani, Goma",
            "structure_name": "Hopital Saint Joseph",
            "legal_form": "association",
            "beneficiary_count": "120",
            "contact_title": "mrs",
            "contact_last_name": "DUPONT",
            "contact_first_name": "Alice",
            "contact_email": "alice@example.org",
            "contact_phone": "+33123456789",
            "address_line1": "1 Rue Principale",
            "address_line2": "",
            "postal_code": "",
            "city": "Paris",
            "country": "France",
            "message": "Besoin d'une desserte mensuelle.",
        }

    def test_valid_request_creates_traceable_request_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            request = submit_stopover_feasibility_request(
                self._valid_payload(),
                source="public_account_request",
            )

        self.assertEqual(StopoverFeasibilityRequest.objects.count(), 1)
        self.assertEqual(request.requested_stopovers, "Kisangani, Goma")
        self.assertEqual(request.structure_name, "Hopital Saint Joseph")
        self.assertEqual(request.beneficiary_count, 120)
        self.assertEqual(request.source, "public_account_request")
        self.assertEqual(PublicAccountRequest.objects.count(), 0)
        self.assertEqual(AssociationRecipient.objects.count(), 0)
        self.assertEqual(ShipmentRecipientOrganization.objects.count(), 0)
        self.assertEqual(PortalAccessGrant.objects.count(), 0)

    def test_required_fields_are_validated(self):
        required_fields = [
            "requester_type",
            "requested_stopovers",
            "structure_name",
            "legal_form",
            "beneficiary_count",
            "contact_title",
            "contact_last_name",
            "contact_first_name",
            "contact_email",
            "contact_phone",
            "address_line1",
            "city",
            "country",
        ]

        for field in required_fields:
            with self.subTest(field=field):
                payload = self._valid_payload()
                payload[field] = ""

                with self.assertRaises(ValidationError) as raised:
                    submit_stopover_feasibility_request(payload)

                self.assertIn(field, raised.exception.message_dict)

    def test_invalid_email_is_rejected(self):
        payload = self._valid_payload()
        payload["contact_email"] = "not-an-email"

        with self.assertRaises(ValidationError) as raised:
            submit_stopover_feasibility_request(payload)

        self.assertIn("contact_email", raised.exception.message_dict)
