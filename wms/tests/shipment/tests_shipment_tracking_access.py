from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from contacts.models import Contact
from wms.models import (
    Destination,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingAuthSource,
    ShipmentTrackingEvent,
    ShipmentTrackingIdentityStatus,
    ShipmentTrackingProofMode,
    ShipmentTrackingStatus,
    VolunteerProfile,
)
from wms.shipment_tracking_access import (
    ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY,
    activate_tracking_access_grant,
    build_tracking_actor_snapshot_from_grant,
    default_tracking_escale_for_shipment,
    find_active_tracking_access_grant,
    normalize_tracking_identifier,
    resolve_active_tracking_access_grant,
    resolve_shipment_contact_for_role,
    resolve_tracking_access_grant_by_email,
    resolve_tracking_access_grant_by_identifier,
    resolve_tracking_identifier_from_grant,
    resolve_tracking_proof_mode,
    shipment_has_boarding_ok,
    tracking_allowed_statuses_for_role,
    tracking_grant_matches_shipment,
    tracking_identifier_label_for_role,
    tracking_pending_account_fields_for_role,
    tracking_requires_structure_details,
    tracking_role_allows_status,
    tracking_status_requires_proof,
)

TEST_PASSWORD = "pass1234"  # pragma: allowlist secret


class ShipmentTrackingAccessGrantTests(TestCase):
    def test_create_tracking_access_grant_for_contact(self):
        user = get_user_model().objects.create_user(
            username="tracking-contact",
            email="contact@example.com",
            password=TEST_PASSWORD,
        )
        contact = Contact.objects.create(
            name="Association Tracking Contact",
            email="contact@example.com",
            is_active=True,
        )

        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )

        self.assertEqual(grant.contact, contact)
        self.assertIsNone(grant.volunteer_profile)
        self.assertEqual(grant.role, ShipmentTrackingAccessRole.SHIPPER)

    @override_settings(SHIPMENT_TRACKING_ACCESS_GRANT_TTL_DAYS=14)
    def test_tracking_access_grant_defaults_to_configured_expiration(self):
        user = get_user_model().objects.create_user(
            username="tracking-expiring",
            email="tracking-expiring@example.com",
            password=TEST_PASSWORD,
        )
        contact = Contact.objects.create(
            name="Expiring Tracking Contact",
            email="tracking-expiring@example.com",
            is_active=True,
        )

        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )

        self.assertIsNotNone(grant.expires_at)
        self.assertGreater(grant.expires_at, timezone.now() + timedelta(days=13))
        self.assertLess(grant.expires_at, timezone.now() + timedelta(days=15))

    def test_create_tracking_access_grant_for_volunteer_profile(self):
        user = get_user_model().objects.create_user(
            username="tracking-volunteer",
            email="volunteer@example.com",
            password=TEST_PASSWORD,
        )
        volunteer_profile = VolunteerProfile.objects.create(user=user)

        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=volunteer_profile,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )

        self.assertEqual(grant.volunteer_profile, volunteer_profile)
        self.assertIsNone(grant.contact)
        self.assertEqual(grant.role, ShipmentTrackingAccessRole.VOLUNTEER)

    def test_build_tracking_actor_snapshot_from_contact_grant(self):
        user = get_user_model().objects.create_user(
            username="tracking-correspondent",
            email="actor@example.com",
            password=TEST_PASSWORD,
        )
        contact = Contact.objects.create(
            name="Correspondent Structure",
            email="actor@example.com",
            is_active=True,
        )
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.CORRESPONDENT,
            contact=contact,
            identity_status=ShipmentTrackingIdentityStatus.PENDING,
        )

        snapshot = build_tracking_actor_snapshot_from_grant(grant)

        self.assertEqual(snapshot["role"], ShipmentTrackingAccessRole.CORRESPONDENT)
        self.assertEqual(snapshot["identifier"], contact.asf_id)
        self.assertEqual(snapshot["email"], "actor@example.com")
        self.assertEqual(snapshot["identity_status"], ShipmentTrackingIdentityStatus.PENDING)
        self.assertEqual(snapshot["auth_source"], ShipmentTrackingAuthSource.QR_RESTRICTED)

    def test_build_tracking_actor_snapshot_from_volunteer_grant_uses_volunteer_id(self):
        user = get_user_model().objects.create_user(
            username="tracking-volunteer-snapshot",
            email="volunteer-actor@example.com",
            password=TEST_PASSWORD,
        )
        volunteer_profile = VolunteerProfile.objects.create(user=user)
        grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=volunteer_profile,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )

        snapshot = build_tracking_actor_snapshot_from_grant(grant)

        self.assertEqual(snapshot["role"], ShipmentTrackingAccessRole.VOLUNTEER)
        self.assertEqual(snapshot["identifier"], str(volunteer_profile.volunteer_id))
        self.assertEqual(snapshot["identity_status"], ShipmentTrackingIdentityStatus.VERIFIED)

    def test_shipment_tracking_event_metadata_defaults(self):
        user = get_user_model().objects.create_user(
            username="tracking-event",
            email="event@example.com",
            password=TEST_PASSWORD,
        )
        shipment = Shipment.objects.create(
            reference="SHP-TRACK-001",
            shipper_name="ASF",
            recipient_name="Hopital",
            destination_address="1 rue du test",
            destination_country="France",
            created_by=user,
        )

        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNING_OK,
            actor_name="Ops",
            actor_structure="ASF",
            comments="",
            created_by=user,
        )

        self.assertEqual(event.actor_role, "")
        self.assertEqual(event.actor_identifier, "")
        self.assertEqual(event.actor_email, "")
        self.assertEqual(event.actor_identity_status, "")
        self.assertEqual(event.auth_source, "")
        self.assertEqual(event.escale_code, "")
        self.assertEqual(event.actor_snapshot, {})
        self.assertEqual(event.proof_mode, "")
        self.assertEqual(event.proof_carton_reference, "")
        self.assertFalse(bool(event.proof_file))

    def test_tracking_helper_role_status_and_proof_rules(self):
        statuses = [
            ShipmentTrackingStatus.PLANNING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ]

        self.assertEqual(normalize_tracking_identifier(" ASF-1 "), "ASF-1")
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.VOLUNTEER),
            "ID bénévole",
        )
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.SHIPPER),
            "ID ASF",
        )
        self.assertEqual(tracking_identifier_label_for_role("unknown"), "Identifiant")
        self.assertEqual(tracking_allowed_statuses_for_role("", statuses), statuses)
        self.assertEqual(tracking_allowed_statuses_for_role("unknown", statuses), [])
        self.assertEqual(
            tracking_allowed_statuses_for_role(ShipmentTrackingAccessRole.CORRESPONDENT, statuses),
            [ShipmentTrackingStatus.RECEIVED_CORRESPONDENT],
        )
        self.assertTrue(tracking_role_allows_status("", "custom"))
        self.assertFalse(tracking_role_allows_status("unknown", ShipmentTrackingStatus.PLANNING_OK))
        self.assertTrue(
            tracking_role_allows_status(
                ShipmentTrackingAccessRole.RECIPIENT,
                ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            )
        )
        self.assertTrue(
            tracking_status_requires_proof(ShipmentTrackingStatus.RECEIVED_CORRESPONDENT)
        )
        self.assertFalse(tracking_status_requires_proof(ShipmentTrackingStatus.PLANNING_OK))
        self.assertIn(
            "structure_name",
            tracking_pending_account_fields_for_role(ShipmentTrackingAccessRole.SHIPPER),
        )
        self.assertEqual(tracking_pending_account_fields_for_role("unknown"), {"role", "email"})
        self.assertTrue(tracking_requires_structure_details(ShipmentTrackingAccessRole.RECIPIENT))
        self.assertFalse(tracking_requires_structure_details(ShipmentTrackingAccessRole.VOLUNTEER))
        self.assertEqual(
            resolve_tracking_proof_mode(proof_no_photo=True, proof_file=None),
            ShipmentTrackingProofMode.MANUAL,
        )
        self.assertEqual(
            resolve_tracking_proof_mode(proof_no_photo=False, proof_file=object()),
            ShipmentTrackingProofMode.PHOTO,
        )
        self.assertEqual(resolve_tracking_proof_mode(proof_no_photo=False, proof_file=None), "")

    @override_settings(TRACKING_CONTACT_IDENTIFIER_LABEL="Tracking ref.")
    def test_tracking_helper_uses_configured_label_for_contact_roles_only(self):
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.SHIPPER),
            "Tracking ref.",
        )
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.RECIPIENT),
            "Tracking ref.",
        )
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.CORRESPONDENT),
            "Tracking ref.",
        )
        self.assertEqual(
            tracking_identifier_label_for_role(ShipmentTrackingAccessRole.VOLUNTEER),
            "ID bénévole",
        )
        self.assertEqual(tracking_identifier_label_for_role("unknown"), "Identifiant")

    def test_default_escale_stays_cdg_until_boarding_then_uses_destination_iata(self):
        user = get_user_model().objects.create_user(
            username="tracking-escale",
            email="tracking-escale@example.com",
            password=TEST_PASSWORD,
        )
        correspondent = Contact.objects.create(
            name="Correspondant ABJ",
            email="abj@example.com",
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="abj",
            country="CI",
            correspondent_contact=correspondent,
        )
        shipment = Shipment.objects.create(
            reference="SHP-TRACK-ESCALE",
            shipper_name="ASF",
            recipient_name="Hopital",
            destination=destination,
            destination_address="1 rue du test",
            destination_country="CI",
            created_by=user,
        )

        self.assertFalse(shipment_has_boarding_ok(None))
        self.assertEqual(default_tracking_escale_for_shipment(shipment), "CDG")

        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Ops",
            actor_structure="ASF",
            created_by=user,
        )

        self.assertTrue(shipment_has_boarding_ok(shipment))
        self.assertEqual(default_tracking_escale_for_shipment(shipment), "ABJ")

        shipment_without_destination = Shipment.objects.create(
            reference="SHP-TRACK-SHIPPED",
            shipper_name="ASF",
            recipient_name="Hopital",
            status=ShipmentStatus.SHIPPED,
            destination_address="1 rue du test",
            destination_country="CI",
            created_by=user,
        )
        self.assertEqual(default_tracking_escale_for_shipment(shipment_without_destination), "CDG")

    def test_tracking_grant_lookup_session_and_matching_helpers(self):
        user = get_user_model().objects.create_user(
            username="tracking-lookup",
            email="lookup@example.com",
            password=TEST_PASSWORD,
        )
        contact = Contact.objects.create(
            name="Lookup Structure",
            email="lookup@example.com",
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name="Correspondant DKR",
            email="dkr@example.com",
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="SN",
            correspondent_contact=correspondent,
        )
        shipment = Shipment.objects.create(
            reference="SHP-TRACK-LOOKUP",
            shipper_name=contact.name,
            shipper_contact_ref=contact,
            recipient_name="Hopital",
            destination=destination,
            destination_address="1 rue du test",
            destination_country="SN",
            created_by=user,
        )
        contact_grant = ShipmentTrackingAccessGrant.objects.create(
            user=user,
            role=ShipmentTrackingAccessRole.SHIPPER,
            contact=contact,
            destination=destination,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )
        volunteer_user = get_user_model().objects.create_user(
            username="tracking-volunteer-lookup",
            email="volunteer-lookup@example.com",
            password=TEST_PASSWORD,
        )
        volunteer_profile = VolunteerProfile.objects.create(user=volunteer_user)
        volunteer_grant = ShipmentTrackingAccessGrant.objects.create(
            user=volunteer_user,
            role=ShipmentTrackingAccessRole.VOLUNTEER,
            volunteer_profile=volunteer_profile,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
        )
        inactive_grant = ShipmentTrackingAccessGrant.objects.create(
            user=get_user_model().objects.create_user(
                username="tracking-inactive-grant",
                email="inactive-grant@example.com",
                password=TEST_PASSWORD,
            ),
            role=ShipmentTrackingAccessRole.RECIPIENT,
            contact=Contact.objects.create(name="Inactive", email="inactive@example.com"),
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
            is_active=False,
        )
        expired_contact = Contact.objects.create(
            name="Expired",
            email="expired@example.com",
            is_active=True,
        )
        expired_grant = ShipmentTrackingAccessGrant.objects.create(
            user=get_user_model().objects.create_user(
                username="tracking-expired-grant",
                email="expired-grant@example.com",
                password=TEST_PASSWORD,
            ),
            role=ShipmentTrackingAccessRole.CORRESPONDENT,
            contact=expired_contact,
            identity_status=ShipmentTrackingIdentityStatus.VERIFIED,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(resolve_tracking_identifier_from_grant(contact_grant), contact.asf_id)
        self.assertEqual(
            resolve_tracking_identifier_from_grant(volunteer_grant),
            str(volunteer_profile.volunteer_id),
        )
        self.assertIsNone(find_active_tracking_access_grant(user=None, role=""))
        self.assertEqual(
            find_active_tracking_access_grant(
                user=user,
                role=ShipmentTrackingAccessRole.SHIPPER,
                contact=contact,
                destination=destination,
            ),
            contact_grant,
        )
        self.assertIsNone(resolve_tracking_access_grant_by_identifier(role="", identifier=""))
        self.assertEqual(
            resolve_tracking_access_grant_by_identifier(
                role=ShipmentTrackingAccessRole.SHIPPER,
                identifier=contact.asf_id.lower(),
            ),
            contact_grant,
        )
        self.assertIsNone(
            resolve_tracking_access_grant_by_identifier(
                role=ShipmentTrackingAccessRole.VOLUNTEER,
                identifier="not-a-number",
            )
        )
        self.assertEqual(
            resolve_tracking_access_grant_by_identifier(
                role=ShipmentTrackingAccessRole.VOLUNTEER,
                identifier=str(volunteer_profile.volunteer_id),
            ),
            volunteer_grant,
        )
        self.assertIsNone(resolve_tracking_access_grant_by_email(role="", email=""))
        self.assertEqual(
            resolve_tracking_access_grant_by_email(
                role=ShipmentTrackingAccessRole.SHIPPER,
                email="LOOKUP@example.com",
            ),
            contact_grant,
        )
        self.assertIsNone(
            resolve_tracking_access_grant_by_identifier(
                role=ShipmentTrackingAccessRole.CORRESPONDENT,
                identifier=expired_contact.asf_id,
            )
        )
        self.assertIsNone(
            resolve_tracking_access_grant_by_email(
                role=ShipmentTrackingAccessRole.CORRESPONDENT,
                email=expired_grant.user.email,
            )
        )

        request = SimpleNamespace(user=user, session={})
        self.assertIsNone(resolve_active_tracking_access_grant(request))
        activate_tracking_access_grant(request, grant=contact_grant)
        self.assertEqual(
            request.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY],
            contact_grant.id,
        )
        self.assertEqual(resolve_active_tracking_access_grant(request), contact_grant)
        request.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = inactive_grant.id
        self.assertIsNone(resolve_active_tracking_access_grant(request))
        request.session[ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY] = expired_grant.id
        self.assertIsNone(resolve_active_tracking_access_grant(request))
        activate_tracking_access_grant(request, grant=None)
        self.assertNotIn(ACTIVE_SHIPMENT_TRACKING_GRANT_SESSION_KEY, request.session)

        self.assertEqual(
            resolve_shipment_contact_for_role(
                shipment=shipment,
                role=ShipmentTrackingAccessRole.SHIPPER,
            ),
            contact,
        )
        self.assertIsNone(resolve_shipment_contact_for_role(shipment=None, role=""))
        self.assertTrue(
            tracking_grant_matches_shipment(
                grant=contact_grant,
                shipment=shipment,
                role=ShipmentTrackingAccessRole.SHIPPER,
                identifier=contact.asf_id,
            )
        )
        self.assertFalse(
            tracking_grant_matches_shipment(
                grant=contact_grant,
                shipment=shipment,
                role=ShipmentTrackingAccessRole.RECIPIENT,
                identifier=contact.asf_id,
            )
        )
        self.assertFalse(
            tracking_grant_matches_shipment(
                grant=contact_grant,
                shipment=shipment,
                role=ShipmentTrackingAccessRole.SHIPPER,
                identifier="wrong",
            )
        )
        self.assertTrue(
            tracking_grant_matches_shipment(
                grant=volunteer_grant,
                shipment=shipment,
                role=ShipmentTrackingAccessRole.VOLUNTEER,
            )
        )
        self.assertEqual(
            resolve_tracking_identifier_from_grant(
                SimpleNamespace(
                    contact_id=None,
                    volunteer_profile_id=1,
                    volunteer_profile=SimpleNamespace(volunteer_id=None),
                )
            ),
            "",
        )
        self.assertFalse(shipment_has_boarding_ok(SimpleNamespace(status="", tracking_events=None)))
        self.assertIsNone(
            resolve_active_tracking_access_grant(
                SimpleNamespace(user=SimpleNamespace(is_authenticated=False), session={})
            )
        )
        self.assertIsNone(resolve_shipment_contact_for_role(shipment=shipment, role="unknown"))
