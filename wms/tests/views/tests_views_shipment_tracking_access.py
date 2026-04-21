from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact
from wms.models import (
    Shipment,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingIdentityStatus,
)

TEST_PASSWORD = "QrAccess123!"  # pragma: allowlist secret


class ShipmentTrackingAccessViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tracking-actor@example.com",
            email="tracking-actor@example.com",
            password=TEST_PASSWORD,
        )
        self.contact = Contact.objects.create(
            name="Structure Tracking",
            email=self.user.email,
            is_active=True,
        )
        self.shipment = Shipment.objects.create(
            reference="SHP-QR-001",
            shipper_name=self.contact.name,
            shipper_contact_ref=self.contact,
            recipient_name="Hopital Test",
            destination_address="1 rue test",
            destination_country="France",
        )
        self.grant = ShipmentTrackingAccessGrant.objects.create(
            user=self.user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=self.contact,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )
        self.next_url = (
            reverse("scan:scan_shipment_track", args=[self.shipment.tracking_token])
            + f"?role={ShipmentTrackingAccessRole.SHIPPER}&identifier={self.contact.asf_id}"
        )

    def _set_password_url(self, user, token=None):
        token = token or default_token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        return reverse("scan:scan_shipment_tracking_access_set_password", args=[uidb64, token])

    def test_qr_access_login_get_renders(self):
        response = self.client.get(reverse("scan:scan_shipment_tracking_access_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="identifier"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, "Connexion suivi")

    def test_qr_access_login_get_prefills_identifier_from_gateway(self):
        response = self.client.get(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "identifier": self.contact.asf_id,
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "next": self.next_url,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.contact.asf_id}"')
        self.assertContains(response, f'value="{ShipmentTrackingAccessRole.SHIPPER}"')

    def test_qr_access_login_post_authenticates_restricted_grant_user(self):
        response = self.client.post(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "identifier": self.contact.asf_id,
                "password": TEST_PASSWORD,
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "next": self.next_url,
            },
        )

        self.assertRedirects(response, self.next_url)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_qr_access_recovery_post_keeps_generic_success_for_unknown_email(self):
        with mock.patch(
            "wms.views_shipment_tracking_access.send_or_enqueue_email_safe"
        ) as send_mock:
            response = self.client.post(
                reverse("scan:scan_shipment_tracking_access_recovery"),
                {
                    "email": "unknown@example.com",
                    "role": ShipmentTrackingAccessRole.SHIPPER,
                    "escale_code": "CDG",
                    "tracking_token": str(self.shipment.tracking_token),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Si votre email est reconnu")
        send_mock.assert_not_called()

    def test_qr_access_recovery_post_sends_email_for_matching_restricted_grant_user(self):
        with mock.patch(
            "wms.views_shipment_tracking_access.send_or_enqueue_email_safe",
            return_value=True,
        ) as send_mock:
            response = self.client.post(
                reverse("scan:scan_shipment_tracking_access_recovery"),
                {
                    "email": self.user.email.upper(),
                    "role": ShipmentTrackingAccessRole.SHIPPER,
                    "escale_code": "CDG",
                    "tracking_token": str(self.shipment.tracking_token),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Si votre email est reconnu")
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.kwargs["recipient"], [self.user.email])
        self.assertIn(self.contact.asf_id, send_mock.call_args.kwargs["message"])
        self.assertIn("expéditeur", send_mock.call_args.kwargs["message"].lower())
        self.assertIn(
            reverse("scan:scan_shipment_track", args=[self.shipment.tracking_token]),
            send_mock.call_args.kwargs["message"],
        )

    def test_qr_access_set_password_redirects_back_to_tracking_route(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        url = f"{self._set_password_url(self.user)}?next={self.next_url}&grant={self.grant.id}"

        response = self.client.post(
            url,
            {
                "new_password1": TEST_PASSWORD,
                "new_password2": TEST_PASSWORD,
            },
        )

        self.assertRedirects(response, self.next_url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(TEST_PASSWORD))
