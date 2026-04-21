from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact
from wms import views_shipment_tracking_access as access_views
from wms.models import (
    Shipment,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingIdentityStatus,
    VolunteerProfile,
)
from wms.shipment_tracking_access import ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY

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
        self.factory = RequestFactory()
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
        self.assertEqual(
            self.client.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY],
            self.grant.id,
        )

    def test_qr_access_login_authenticated_user_activates_matching_grant(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "identifier": self.contact.asf_id,
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "next": self.next_url,
            },
        )

        self.assertRedirects(response, self.next_url)
        self.assertEqual(
            self.client.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY],
            self.grant.id,
        )

    def test_qr_access_login_post_reports_required_and_invalid_credentials(self):
        response_required = self.client.post(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "identifier": "",
                "password": "",
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "next": self.next_url,
            },
        )
        self.assertEqual(response_required.status_code, 200)
        self.assertContains(response_required, "Identifiant et mot de passe requis.")

        response_invalid = self.client.post(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "identifier": self.contact.asf_id,
                "password": "wrong-password",  # pragma: allowlist secret
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "next": self.next_url,
            },
        )
        self.assertEqual(response_invalid.status_code, 200)
        self.assertContains(response_invalid, "Identifiants invalides.")

    def test_qr_access_internal_helpers_reject_unsafe_or_unmatched_inputs(self):
        request = self.factory.get(
            reverse("scan:scan_shipment_tracking_access_login"),
            {
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "identifier": self.contact.asf_id,
            },
        )
        other_user = get_user_model().objects.create_user(
            username="tracking-other-user",
            email="tracking-other-user@example.com",
            password=TEST_PASSWORD,
        )
        inactive_user = get_user_model().objects.create_user(
            username="tracking-inactive-user",
            email="tracking-inactive-user@example.com",
            password=TEST_PASSWORD,
            is_active=False,
        )

        self.assertEqual(access_views._safe_next_url(request, "https://evil.example/scan"), "")
        self.assertEqual(access_views._merge_next_url_query("", request), "")
        self.assertIsNone(access_views._get_user_from_uidb64("not-valid-uid"))
        self.assertIsNone(
            access_views._tracking_access_grant_from_request(request, user=other_user)
        )
        user, grant = access_views._authenticate_tracking_user(
            request,
            identifier="missing@example.com",
            password=TEST_PASSWORD,
            role=ShipmentTrackingAccessRole.SHIPPER,
        )
        self.assertIsNone(user)
        self.assertIsNone(grant)
        user, grant = access_views._authenticate_tracking_user(
            request,
            identifier=self.contact.asf_id,
            password="wrong-password",  # pragma: allowlist secret
            role=ShipmentTrackingAccessRole.SHIPPER,
        )
        self.assertIsNone(user)
        self.assertIsNone(grant)

        reactivated = access_views._get_or_create_tracking_user(
            email=inactive_user.email,
            role=ShipmentTrackingAccessRole.SHIPPER,
            identifier=self.contact.asf_id,
        )

        reactivated.refresh_from_db()
        self.assertTrue(reactivated.is_active)

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

    def test_qr_access_recovery_post_requires_email(self):
        response = self.client.post(
            reverse("scan:scan_shipment_tracking_access_recovery"),
            {
                "email": "",
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "escale_code": "CDG",
                "tracking_token": str(self.shipment.tracking_token),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email requis.")

    def test_qr_access_recovery_internal_helper_edges(self):
        volunteer_without_profile = get_user_model().objects.create_user(
            username="tracking-volunteer-no-profile",
            email="tracking-volunteer-no-profile@example.com",
            password=TEST_PASSWORD,
        )
        volunteer_with_grant = get_user_model().objects.create_user(
            username="tracking-volunteer-existing-grant",
            email="tracking-volunteer-existing-grant@example.com",
            password=TEST_PASSWORD,
        )
        profile = VolunteerProfile.objects.create(user=volunteer_with_grant, is_active=True)
        existing_grant = ShipmentTrackingAccessGrant.objects.create(
            user=volunteer_with_grant,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=profile,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )
        shipment_without_correspondent = Shipment.objects.create(
            reference="SHP-QR-NO-CORR",
            shipper_name="Structure Tracking",
            recipient_name="Hopital Test",
            destination_address="1 rue test",
            destination_country="France",
        )

        self.assertIsNone(
            access_views._resolve_recovery_grant(
                shipment=self.shipment,
                email="unknown-volunteer@example.com",
                role=ShipmentTrackingAccessRole.VOLUNTEER,
            )
        )
        self.assertIsNone(
            access_views._resolve_recovery_grant(
                shipment=self.shipment,
                email=volunteer_without_profile.email,
                role=ShipmentTrackingAccessRole.VOLUNTEER,
            )
        )
        self.assertEqual(
            access_views._resolve_recovery_grant(
                shipment=self.shipment,
                email=volunteer_with_grant.email,
                role=ShipmentTrackingAccessRole.VOLUNTEER,
            ),
            existing_grant,
        )
        self.assertIsNone(
            access_views._resolve_recovery_grant(
                shipment=shipment_without_correspondent,
                email="correspondent@example.com",
                role=ShipmentTrackingAccessRole.CORRESPONDENT,
            )
        )

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

    def test_qr_access_recovery_post_creates_contact_grant_for_matching_party_email(self):
        recipient = Contact.objects.create(
            name="Recipient Tracking",
            email="recipient-tracking@example.com",
            is_active=True,
        )
        shipment = Shipment.objects.create(
            reference="SHP-QR-RECIPIENT",
            shipper_name="Structure Tracking",
            recipient_name=recipient.name,
            recipient_contact_ref=recipient,
            destination_address="1 rue test",
            destination_country="France",
        )

        with mock.patch(
            "wms.views_shipment_tracking_access.send_or_enqueue_email_safe",
            return_value=True,
        ) as send_mock:
            response = self.client.post(
                reverse("scan:scan_shipment_tracking_access_recovery"),
                {
                    "email": recipient.email.upper(),
                    "role": ShipmentTrackingAccessRole.RECIPIENT,
                    "escale_code": "DKR",
                    "tracking_token": str(shipment.tracking_token),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ShipmentTrackingAccessGrant.objects.filter(
                role=ShipmentTrackingAccessRole.RECIPIENT,
                contact=recipient,
                user__email=recipient.email,
                identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
            ).exists()
        )
        send_mock.assert_called_once()
        self.assertIn(recipient.asf_id, send_mock.call_args.kwargs["message"])
        self.assertIn("DKR", send_mock.call_args.kwargs["message"])

    def test_qr_access_recovery_post_creates_volunteer_grant_for_profile(self):
        volunteer_user = get_user_model().objects.create_user(
            username="tracking-volunteer-recovery",
            email="tracking-volunteer-recovery@example.com",
            password=TEST_PASSWORD,
        )
        profile = VolunteerProfile.objects.create(user=volunteer_user, is_active=False)

        with mock.patch(
            "wms.views_shipment_tracking_access.send_or_enqueue_email_safe",
            return_value=True,
        ) as send_mock:
            response = self.client.post(
                reverse("scan:scan_shipment_tracking_access_recovery"),
                {
                    "email": volunteer_user.email,
                    "role": ShipmentTrackingAccessRole.VOLUNTEER,
                    "escale_code": "CDG",
                    "tracking_token": str(self.shipment.tracking_token),
                },
            )

        self.assertEqual(response.status_code, 200)
        grant = ShipmentTrackingAccessGrant.objects.get(
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=profile,
        )
        self.assertEqual(grant.identity_status, ShipmentTrackingIdentityStatus.PENDING)
        send_mock.assert_called_once()
        self.assertIn(str(profile.volunteer_id), send_mock.call_args.kwargs["message"])

    def test_qr_access_set_password_get_rejects_invalid_token(self):
        url = self._set_password_url(self.user, token="invalid-token")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lien invalide")

    def test_qr_access_set_password_redirects_back_to_tracking_route(self):
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        base_next = reverse("scan:scan_shipment_track", args=[self.shipment.tracking_token])
        url = f"{self._set_password_url(self.user)}?next={base_next}&grant={self.grant.id}"

        response = self.client.post(
            url,
            {
                "new_password1": TEST_PASSWORD,
                "new_password2": TEST_PASSWORD,
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "identifier": self.contact.asf_id,
            },
        )

        self.assertRedirects(response, self.next_url)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(TEST_PASSWORD))
        self.assertEqual(
            self.client.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY],
            self.grant.id,
        )

    def test_qr_access_logout_clears_restricted_session(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = self.grant.id
        session.save()

        response = self.client.post(reverse("scan:scan_shipment_tracking_access_logout"))

        self.assertRedirects(response, reverse("scan:scan_shipment_tracking_access_login"))
        self.assertNotIn(ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY, self.client.session)
        self.assertNotIn("_auth_user_id", self.client.session)
