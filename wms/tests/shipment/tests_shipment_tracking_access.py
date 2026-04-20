from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact
from wms.models import (
    Shipment,
    ShipmentTrackingAccessGrant,
    ShipmentTrackingAccessRole,
    ShipmentTrackingAuthSource,
    ShipmentTrackingEvent,
    ShipmentTrackingIdentityStatus,
    ShipmentTrackingStatus,
    VolunteerProfile,
)
from wms.shipment_tracking_access import build_tracking_actor_snapshot_from_grant

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
