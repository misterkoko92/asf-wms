from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    CommunicationDraft,
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
    Shipment,
    ShipmentStatus,
)
from wms.planning.communication_actions import (
    build_draft_helper_action_payload,
    build_family_helper_action_payload,
)
from wms.planning.communications import generate_version_drafts
from wms.planning.legacy_communications import CommunicationFamily


class PlanningCommunicationActionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="communication-actions-planner",
            email="communication-actions@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Actions communications semaine 11",
            is_current=True,
            created_by=self.user,
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=self.user,
        )
        self.shipment = Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name="Hopital Saint Joseph",
            recipient_name="Centre Medical",
            destination_address="1 Rue Test",
            destination_country="Cameroun",
            created_by=self.user,
        )
        self.shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment=self.shipment,
            shipment_reference=self.shipment.reference,
            shipper_name="Hopital Saint Joseph",
            destination_iata="NSI",
            carton_count=10,
            equivalent_units=12,
            payload={
                "destination_city": "YAOUNDE",
                "legacy_type": "MM",
                "legacy_destinataire": "Centre Medical",
                "shipper_reference": {
                    "contact_name": "Hopital Saint Joseph",
                    "notification_emails": ["expediteur@example.com"],
                },
                "recipient_reference": {
                    "contact_name": "Centre Medical",
                    "notification_emails": ["destinataire@example.com"],
                },
                "correspondent_reference": {
                    "contact_name": "Jean Dupont",
                    "contact_title": "M.",
                    "contact_first_name": "Jean",
                    "contact_last_name": "Dupont",
                    "notification_emails": ["correspondant@example.com"],
                    "phone": "0601020304",
                },
            },
        )
        self.volunteer = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="COURTOIS Alain",
            payload={"phone": "0611223344", "first_name": "Alain", "last_name": "COURTOIS"},
        )
        self.flight = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF908",
            departure_date="2026-03-09",
            destination_iata="NSI",
            capacity_units=20,
            payload={"departure_time": "11:10", "routing": "CDG-NSI"},
        )

    def make_version(self, *, based_on=None):
        return PlanningVersion.objects.create(
            run=self.run,
            based_on=based_on,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )

    def add_assignment(self, version):
        return PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=self.shipment_snapshot,
            volunteer_snapshot=self.volunteer,
            flight_snapshot=self.flight,
            assigned_carton_count=10,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )

    def draft_for_family(self, version, family):
        return CommunicationDraft.objects.get(version=version, family=family)

    def test_build_draft_helper_action_payload_for_whatsapp_exposes_message_without_subject(self):
        version = self.make_version()
        self.add_assignment(version)
        generate_version_drafts(version)

        payload = build_draft_helper_action_payload(
            self.draft_for_family(version, CommunicationFamily.WHATSAPP_BENEVOLE)
        )

        self.assertEqual(payload["action"], "whatsapp")
        self.assertEqual(payload["family"], CommunicationFamily.WHATSAPP_BENEVOLE)
        self.assertEqual(payload["recipient_label"], "COURTOIS Alain")
        self.assertEqual(payload["recipient_contact"], "0611223344")
        self.assertTrue(payload["body"].startswith("Bonjour Alain"))
        self.assertNotIn("subject", payload)
        self.assertEqual(payload["attachments"], [])

    def test_build_draft_helper_action_payload_for_internal_emails_uses_excel_workbook(self):
        version = self.make_version()
        self.add_assignment(version)
        generate_version_drafts(version)

        for family, recipient in (
            (CommunicationFamily.EMAIL_ASF, "ASF interne"),
            (CommunicationFamily.EMAIL_AIRFRANCE, "Air France"),
        ):
            with self.subTest(family=family):
                payload = build_draft_helper_action_payload(self.draft_for_family(version, family))

                self.assertEqual(payload["action"], "email")
                self.assertEqual(payload["family"], family)
                self.assertEqual(payload["recipient_label"], recipient)
                self.assertIn("subject", payload)
                self.assertIn("body_html", payload)
                self.assertEqual(
                    payload["attachments"],
                    [
                        {
                            "attachment_type": "excel_workbook",
                            "version_id": version.pk,
                            "filename": f"planning-v{version.number}.xlsx",
                            "optional": False,
                        }
                    ],
                )

    def test_build_draft_helper_action_payload_for_partner_emails_uses_current_shipments(self):
        version = self.make_version()
        self.add_assignment(version)
        generate_version_drafts(version)

        for family in (
            CommunicationFamily.EMAIL_CORRESPONDANT,
            CommunicationFamily.EMAIL_EXPEDITEUR,
            CommunicationFamily.EMAIL_DESTINATAIRE,
        ):
            with self.subTest(family=family):
                payload = build_draft_helper_action_payload(self.draft_for_family(version, family))

                self.assertEqual(payload["action"], "email")
                self.assertEqual(
                    payload["attachments"],
                    [
                        {
                            "attachment_type": "packing_list_pdf",
                            "shipment_snapshot_id": self.shipment_snapshot.pk,
                            "shipment_reference": self.shipment.reference,
                            "filename": f"packing-list-{self.shipment.reference}.pdf",
                            "optional": True,
                        }
                    ],
                )

    def test_build_draft_helper_action_payload_for_cancelled_partner_email_uses_previous_shipments(
        self,
    ):
        previous = self.make_version()
        self.add_assignment(previous)
        current = self.make_version(based_on=previous)
        generate_version_drafts(current)

        for family in (
            CommunicationFamily.EMAIL_CORRESPONDANT,
            CommunicationFamily.EMAIL_EXPEDITEUR,
            CommunicationFamily.EMAIL_DESTINATAIRE,
        ):
            with self.subTest(family=family):
                payload = build_draft_helper_action_payload(self.draft_for_family(current, family))

                self.assertEqual(
                    payload["attachments"],
                    [
                        {
                            "attachment_type": "packing_list_pdf",
                            "shipment_snapshot_id": self.shipment_snapshot.pk,
                            "shipment_reference": self.shipment.reference,
                            "filename": f"packing-list-{self.shipment.reference}.pdf",
                            "optional": True,
                        }
                    ],
                )

    def test_build_family_helper_action_payload_groups_matching_drafts(self):
        version = self.make_version()
        self.add_assignment(version)
        generate_version_drafts(version)

        payload = build_family_helper_action_payload(
            version=version,
            family=CommunicationFamily.EMAIL_EXPEDITEUR,
        )

        self.assertEqual(payload["family"], CommunicationFamily.EMAIL_EXPEDITEUR)
        self.assertEqual(payload["action"], "email")
        self.assertEqual(len(payload["drafts"]), 1)
        self.assertEqual(payload["drafts"][0]["recipient_label"], "Hopital Saint Joseph")
