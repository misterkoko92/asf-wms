from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
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
)
from wms.planning.communications import generate_version_drafts
from wms.planning.legacy_communications import format_correspondent_contact
from wms.planning.version_dashboard import build_version_dashboard


class PlanningLegacyCommunicationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="legacy-comms-planner",
            email="legacy-comms@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Communications semaine 11",
            is_current=True,
            created_by=self.user,
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=self.parameter_set,
            flight_mode="hybrid",
            status=PlanningRunStatus.SOLVED,
            created_by=self.user,
            solver_result={"unassigned_reasons": {}},
        )
        self.version = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )

        self.shipper_contact = Contact.objects.create(
            name="Hopital Saint Joseph",
            contact_type=ContactType.ORGANIZATION,
            email="expediteur@example.com",
            is_active=True,
        )
        self.recipient_contact = Contact.objects.create(
            name="Centre Medical",
            contact_type=ContactType.ORGANIZATION,
            email="destinataire@example.com",
            is_active=True,
        )
        self.correspondent_contact = Contact.objects.create(
            name="Jean Dupont",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            email="correspondant@example.com",
            phone="0601020304",
            phone2="0605060708",
            is_active=True,
        )

        shipper_user = get_user_model().objects.create_user(
            username="shipper-portal@example.com",
            email="shipper-portal@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.association_profile = AssociationProfile.objects.create(
            user=shipper_user,
            contact=self.shipper_contact,
        )
        AssociationPortalContact.objects.create(
            profile=self.association_profile,
            position=1,
            first_name="Alice",
            last_name="Martin",
            email="expediteur@example.com",
            is_shipping=True,
            is_active=True,
        )

        self.shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="260128",
            shipper_name="Hopital Saint Joseph",
            destination_iata="NSI",
            priority=1,
            carton_count=10,
            equivalent_units=10,
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
                    "phone2": "0605060708",
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
        PlanningAssignment.objects.create(
            version=self.version,
            shipment_snapshot=self.shipment,
            volunteer_snapshot=self.volunteer,
            flight_snapshot=self.flight,
            assigned_carton_count=10,
            source=PlanningAssignmentSource.MANUAL,
            sequence=1,
        )

    def _expected_table_html(self) -> str:
        return "\n".join(
            [
                '<table cellpadding="6" cellspacing="0" style="border-collapse:collapse; table-layout:auto; border:1px solid #999;">',
                "<tr>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Date</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Destination</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>N° Vol</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>N° BE</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Colis</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Type</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Expéditeur</th>",
                "<th style='background:#e6e6e6; white-space:nowrap; border:1px solid #999;'>Destinataire</th>",
                "</tr>",
                "<tr>",
                "<td style='white-space:nowrap; border:1px solid #999;'>Lundi 09/03/2026</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>YAOUNDE</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>AF 908</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>260128</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>10</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>MM</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>Hopital Saint Joseph</td>",
                "<td style='white-space:nowrap; border:1px solid #999;'>Centre Medical</td>",
                "</tr>",
                "</table>",
            ]
        )

    def test_generate_version_drafts_builds_legacy_communication_families(self):
        drafts = generate_version_drafts(self.version)

        self.assertEqual(len(drafts), 6)
        self.assertEqual(
            {getattr(draft, "family", "") for draft in drafts},
            {
                "whatsapp_benevole",
                "email_asf",
                "email_airfrance",
                "email_correspondant",
                "email_expediteur",
                "email_destinataire",
            },
        )

    def test_generate_version_drafts_uses_legacy_subjects_and_bodies(self):
        drafts = generate_version_drafts(self.version)
        drafts_by_family = {getattr(draft, "family", ""): draft for draft in drafts}
        table_html = self._expected_table_html()

        whatsapp = drafts_by_family.get("whatsapp_benevole")
        self.assertIsNotNone(whatsapp)
        self.assertEqual(whatsapp.subject, "")
        self.assertEqual(
            whatsapp.body,
            "\n".join(
                [
                    "Bonjour Alain, voici tes mises à bord pour la semaine prochaine :",
                    "• Lundi 9 mars : YAOUNDE // AF 908 // 11h10 // BE 260128 // 10 colis MM",
                    "Total NSI : 10 colis en simple",
                    "",
                    "Merci de me confirmer si tu es OK. N'hésite pas à m'appeler si besoin pour ajuster.",
                    "Merci beaucoup !",
                ]
            ),
        )

        email_asf = drafts_by_family.get("email_asf")
        self.assertIsNotNone(email_asf)
        self.assertEqual(email_asf.subject, "Planning SEMAINE 11 - 2026")
        self.assertEqual(
            email_asf.body,
            (
                "Bonjour à tous,<br><br>"
                "J'espère que vous allez bien !<br><br>"
                "Voici en pièce jointe le planning de la semaine 11.<br><br>"
                "Bonne journée à tous,<br>"
                "Edouard<br>"
            ),
        )

        email_airfrance = drafts_by_family.get("email_airfrance")
        self.assertIsNotNone(email_airfrance)
        self.assertEqual(email_airfrance.subject, "Aviation Sans Frontires / Planning S11")
        self.assertEqual(
            email_airfrance.body,
            (
                "Bonjour,<br><br>"
                "Comme convenu, veuillez trouver ci-joint notre planning des expéditions prévues pour la semaine 11.<br>"
                "Nous vous tiendrons informés en cas de mise à jour le cas échéant.<br><br>"
                "Encore merci à tous pour votre aide,<br><br>"
                "Cordialement,<br>"
                "Edouard<br>"
            ),
        )

        email_correspondant = drafts_by_family.get("email_correspondant")
        self.assertIsNotNone(email_correspondant)
        self.assertEqual(email_correspondant.subject, "ASF / Expédition YAOUNDE / Semaine 11")
        self.assertEqual(
            email_correspondant.body,
            (
                "Bonjour,<br><br>"
                "J'espère que vous allez bien.<br><br>"
                "Voici les informations d'expédition pour la destination : YAOUNDE.<br><br>"
                f"{table_html}<br><br>"
                "Cordialement,<br><br>"
                "Edouard<br>"
            ),
        )

        email_expediteur = drafts_by_family.get("email_expediteur")
        self.assertIsNotNone(email_expediteur)
        self.assertEqual(
            email_expediteur.subject,
            "Hopital Saint Joseph / Expédition YAOUNDE / Semaine 11",
        )
        self.assertEqual(
            email_expediteur.body,
            (
                "Bonjour,<br><br>"
                "Nous tenons à vous informer des livraisons prévues la semaine prochaine pour vos colis :<br><br>"
                f"{table_html}<br><br>"
                "Pouvez-vous demander à votre structure sur place de prendre contact avec notre correspondant "
                "afin d'organiser le transfert des colis ?<br><br>"
                "Coordonnées de notre correspondant :<br>"
                "M. Jean DUPONT / correspondant@example.com / 0601020304 / 0605060708<br><br>"
                "Merci pour votre confiance.<br><br>"
                "Cordialement,<br><br>"
                "Edouard<br>"
            ),
        )

        email_destinataire = drafts_by_family.get("email_destinataire")
        self.assertIsNotNone(email_destinataire)
        self.assertEqual(
            email_destinataire.subject,
            "Centre Medical / Expédition YAOUNDE / Semaine 11",
        )
        self.assertEqual(
            email_destinataire.body,
            (
                "Bonjour,<br><br>"
                "Nous tenons à vous informer des livraisons prévues la semaine prochaine pour vos colis :<br><br>"
                f"{table_html}<br><br>"
                "Pouvez-vous demander à votre structure sur place de prendre contact avec notre correspondant "
                "afin d'organiser le transfert des colis ?<br><br>"
                "Coordonnées de notre correspondant :<br>"
                "M. Jean DUPONT / correspondant@example.com / 0601020304 / 0605060708<br><br>"
                "Merci pour votre confiance.<br><br>"
                "Cordialement,<br><br>"
                "Edouard<br>"
            ),
        )

    def test_build_version_dashboard_groups_communications_by_family(self):
        generate_version_drafts(self.version)

        dashboard = build_version_dashboard(self.version)

        self.assertEqual(
            [group.get("family_key") for group in dashboard["communications"]["groups"]],
            [
                "whatsapp_benevole",
                "email_asf",
                "email_airfrance",
                "email_correspondant",
                "email_expediteur",
                "email_destinataire",
            ],
        )
        self.assertEqual(
            [group.get("family_label") for group in dashboard["communications"]["groups"]],
            [
                "WhatsApp bénévoles",
                "Mail ASF interne",
                "Mail Air France",
                "Mail Correspondants",
                "Mail Expéditeurs",
                "Mail Destinataires",
            ],
        )
        self.assertEqual(
            [
                group["drafts"][0]["recipient_label"]
                for group in dashboard["communications"]["groups"]
            ],
            [
                "COURTOIS Alain",
                "ASF interne",
                "Air France",
                "Jean Dupont",
                "Hopital Saint Joseph",
                "Centre Medical",
            ],
        )
        self.assertTrue(
            all(group["is_priority"] for group in dashboard["communications"]["groups"])
        )
        self.assertFalse(
            any(group["is_collapsed"] for group in dashboard["communications"]["groups"])
        )
        self.assertEqual(dashboard["communications"]["draft_count"], 6)

    def test_generate_version_drafts_persists_recipient_contacts_per_family(self):
        drafts = generate_version_drafts(self.version)
        contacts_by_family = {
            getattr(draft, "family", ""): draft.recipient_contact for draft in drafts
        }

        self.assertEqual(contacts_by_family.get("email_expediteur"), "expediteur@example.com")
        self.assertEqual(contacts_by_family.get("email_destinataire"), "destinataire@example.com")
        self.assertEqual(contacts_by_family.get("email_correspondant"), "correspondant@example.com")
        self.assertEqual(contacts_by_family.get("whatsapp_benevole"), "0611223344")

        self.assertEqual(CommunicationDraft.objects.filter(version=self.version).count(), 6)

    def test_format_correspondent_contact_accepts_empty_notification_emails(self):
        self.assertEqual(
            format_correspondent_contact(
                {
                    "contact_title": "Mme",
                    "contact_first_name": "Claire",
                    "contact_last_name": "Durand",
                    "notification_emails": [],
                    "phone": "0102030405",
                }
            ),
            "Mme Claire DURAND / 0102030405",
        )
