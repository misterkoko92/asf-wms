from django.test import TestCase, override_settings

from contacts.models import Contact
from wms.forms import (
    ShipmentTrackingAccessRecoveryForm,
    ShipmentTrackingForm,
    ShipmentTrackingGatewayForm,
    ShipmentTrackingPendingAccountForm,
)
from wms.models import (
    Destination,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingAccessRole,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ShipmentTrackingGatewayFormTests(TestCase):
    def test_gateway_form_uses_volunteer_identifier_label(self):
        form = ShipmentTrackingGatewayForm(selected_role=ShipmentTrackingAccessRole.VOLUNTEER)

        self.assertEqual(form.fields["identifier"].label, "ID bénévole")

    def test_gateway_form_uses_asf_identifier_label_for_contact_roles(self):
        form = ShipmentTrackingGatewayForm(selected_role=ShipmentTrackingAccessRole.SHIPPER)

        self.assertEqual(form.fields["identifier"].label, "ID ASF")

    @override_settings(TRACKING_CONTACT_IDENTIFIER_LABEL="Tracking ref.")
    def test_gateway_form_uses_configured_identifier_label_for_contact_roles(self):
        form = ShipmentTrackingGatewayForm(selected_role=ShipmentTrackingAccessRole.SHIPPER)

        self.assertEqual(form.fields["identifier"].label, "Tracking ref.")

    @override_settings(TRACKING_CONTACT_IDENTIFIER_LABEL="Tracking ref.")
    def test_gateway_form_keeps_non_contact_identifier_labels(self):
        volunteer_form = ShipmentTrackingGatewayForm(
            selected_role=ShipmentTrackingAccessRole.VOLUNTEER
        )
        fallback_form = ShipmentTrackingGatewayForm()

        self.assertEqual(volunteer_form.fields["identifier"].label, "ID bénévole")
        self.assertEqual(fallback_form.fields["identifier"].label, "Identifiant")


class ShipmentTrackingRecoveryFormTests(TestCase):
    def _create_destination(self, *, iata_code="BGF"):
        correspondent = Contact.objects.create(
            name=f"Correspondant {iata_code}",
            email=f"{iata_code.lower()}@example.com",
            is_active=True,
        )
        return Destination.objects.create(
            city="Bangui",
            iata_code=iata_code,
            country="RCA",
            correspondent_contact=correspondent,
        )

    def _create_shipment(self, *, status=ShipmentStatus.PACKED, destination=None):
        return Shipment.objects.create(
            reference="SHP-RECOVERY-001",
            status=status,
            shipper_name="ASF",
            recipient_name="Hopital Test",
            destination=destination,
            destination_address="1 rue du test",
            destination_country="France",
        )

    def test_recovery_form_defaults_escale_to_cdg_before_boarding_ok(self):
        destination = self._create_destination()
        shipment = self._create_shipment(destination=destination, status=ShipmentStatus.PACKED)

        form = ShipmentTrackingAccessRecoveryForm(shipment=shipment)

        self.assertEqual(form.fields["escale_code"].initial, "CDG")

    def test_recovery_form_defaults_escale_to_destination_after_boarding_ok(self):
        destination = self._create_destination()
        shipment = self._create_shipment(destination=destination, status=ShipmentStatus.SHIPPED)
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Ops",
            actor_structure="ASF",
        )

        form = ShipmentTrackingAccessRecoveryForm(shipment=shipment)

        self.assertEqual(form.fields["escale_code"].initial, "BGF")


class ShipmentTrackingPendingAccountFormTests(TestCase):
    def test_pending_creation_requires_structure_fields_for_shipper(self):
        form = ShipmentTrackingPendingAccountForm(
            data={
                "role": ShipmentTrackingAccessRole.SHIPPER,
                "email": "shipper@example.com",
            },
            selected_role=ShipmentTrackingAccessRole.SHIPPER,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("structure_name", form.errors)
        self.assertIn("address_line1", form.errors)
        self.assertIn("city", form.errors)
        self.assertIn("country", form.errors)

    def test_pending_creation_hides_structure_fields_for_volunteer(self):
        form = ShipmentTrackingPendingAccountForm(
            selected_role=ShipmentTrackingAccessRole.VOLUNTEER
        )

        self.assertNotIn("structure_name", form.fields)
        self.assertNotIn("address_line1", form.fields)
        self.assertNotIn("escale_code", form.fields)
        self.assertIn("first_name", form.fields)
        self.assertIn("last_name", form.fields)


class ShipmentTrackingUpdateFormTests(TestCase):
    def _create_shipment(self):
        correspondent = Contact.objects.create(
            name="Correspondant BGF",
            email="bgf@example.com",
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Bangui",
            iata_code="BGF",
            country="RCA",
            correspondent_contact=correspondent,
        )
        return Shipment.objects.create(
            reference="SHP-UPDATE-001",
            status=ShipmentStatus.SHIPPED,
            shipper_name="ASF",
            recipient_name="Hopital Test",
            destination=destination,
            destination_address="1 rue du test",
            destination_country="France",
        )

    def test_received_correspondent_requires_photo_or_manual_carton_reference(self):
        shipment = self._create_shipment()
        form = ShipmentTrackingForm(
            data={
                "status": ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
                "actor_name": "Correspondant",
                "actor_structure": "Escal",
                "comments": "",
                "proof_no_photo": "on",
                "proof_carton_reference": "",
            },
            shipment=shipment,
            actor_role=ShipmentTrackingAccessRole.CORRESPONDENT,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("proof_carton_reference", form.errors)

    def test_received_recipient_requires_photo_or_manual_carton_reference(self):
        shipment = self._create_shipment()
        form = ShipmentTrackingForm(
            data={
                "status": ShipmentTrackingStatus.RECEIVED_RECIPIENT,
                "actor_name": "Destinataire",
                "actor_structure": "Hopital",
                "comments": "",
                "proof_no_photo": "on",
                "proof_carton_reference": "",
            },
            shipment=shipment,
            actor_role=ShipmentTrackingAccessRole.RECIPIENT,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("proof_carton_reference", form.errors)
