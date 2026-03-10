import json
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    Carton,
    CartonItem,
    Destination,
    Flight,
    FlightSourceBatch,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    Product,
    ProductCategory,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentUnitEquivalenceRule,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
    Warehouse,
)
from wms.planning.recipe_export import build_planning_recipe_export


class PlanningRecipeExportTests(TestCase):
    def setUp(self):
        self.week_start = date(2026, 3, 9)
        self.week_end = date(2026, 3, 15)
        self.user_model = get_user_model()
        self.planner = self.user_model.objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PlanningParameterSet.objects.create(
            name="Phase 3 S11",
            is_current=True,
            created_by=self.planner,
        )
        self.other_parameter_set = PlanningParameterSet.objects.create(
            name="Old set",
            is_current=False,
            created_by=self.planner,
        )

        self.shipper_contact = Contact.objects.create(
            name="Association Lumiere",
            contact_type=ContactType.ORGANIZATION,
            email="contact@lumiere.example",
            is_active=True,
        )
        self.recipient_contact = Contact.objects.create(
            name="Recipient ABJ",
            contact_type=ContactType.PERSON,
            email="recipient@example.com",
            first_name="Recipient",
            last_name="ABJ",
            is_active=True,
        )
        self.correspondent_abj = Contact.objects.create(
            name="Correspondent ABJ",
            contact_type=ContactType.ORGANIZATION,
            email="abj@example.com",
            is_active=True,
        )
        self.correspondent_dkr = Contact.objects.create(
            name="Correspondent DKR",
            contact_type=ContactType.ORGANIZATION,
            email="dkr@example.com",
            is_active=True,
        )
        self.destination_abj = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="Cote d'Ivoire",
            correspondent_contact=self.correspondent_abj,
            is_active=True,
        )
        self.destination_dkr = Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=self.correspondent_dkr,
            is_active=True,
        )
        PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination_abj,
            label="ABJ weekly",
            weekly_frequency=2,
            max_cartons_per_flight=12,
            priority=1,
        )
        PlanningDestinationRule.objects.create(
            parameter_set=self.other_parameter_set,
            destination=self.destination_dkr,
            label="DKR archived",
            weekly_frequency=1,
            max_cartons_per_flight=10,
            priority=5,
        )

        self.association_user = self.user_model.objects.create_user(
            username="association@example.com",
            email="association@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        other_contact = Contact.objects.create(
            name="Association Hors Scope",
            contact_type=ContactType.ORGANIZATION,
            email="other@example.com",
            is_active=True,
        )
        other_user = self.user_model.objects.create_user(
            username="other-association@example.com",
            email="other-association@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        other_profile = AssociationProfile.objects.create(
            user=other_user,
            contact=other_contact,
            notification_emails="other-ops@example.com",
        )
        AssociationPortalContact.objects.create(
            profile=other_profile,
            first_name="Ghost",
            last_name="Portal",
            email="ghost@example.com",
            is_shipping=True,
        )
        self.association_profile = AssociationProfile.objects.create(
            user=self.association_user,
            contact=self.shipper_contact,
            notification_emails="ops@example.com",
        )
        AssociationPortalContact.objects.create(
            profile=self.association_profile,
            first_name="Alice",
            last_name="Ops",
            email="shipping@example.com",
            is_shipping=True,
        )

        self.volunteer_user = self.user_model.objects.create_user(
            username="volunteer@example.com",
            email="volunteer@example.com",
            first_name="Camille",
            last_name="Martin",
            password="pass1234",  # pragma: allowlist secret
        )
        self.volunteer = VolunteerProfile.objects.create(user=self.volunteer_user, is_active=True)
        VolunteerConstraint.objects.create(volunteer=self.volunteer, max_colis_vol=4)
        VolunteerAvailability.objects.create(
            volunteer=self.volunteer,
            date=self.week_start + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(13, 0),
        )
        inactive_user = self.user_model.objects.create_user(
            username="inactive@example.com",
            email="inactive@example.com",
            first_name="Inactive",
            last_name="Volunteer",
            password="pass1234",  # pragma: allowlist secret
        )
        VolunteerProfile.objects.create(user=inactive_user, is_active=False)

        self.shipment_in_week = self._create_shipment(
            reference="EXP-RECIPE-001",
            ready_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            destination=self.destination_abj,
            status=ShipmentStatus.PACKED,
        )
        self._create_shipment(
            reference="EXP-RECIPE-OUTSIDE",
            ready_at=datetime(2026, 3, 20, 9, 0, tzinfo=UTC),
            destination=self.destination_dkr,
            status=ShipmentStatus.PACKED,
        )

        self.batch_in_week = FlightSourceBatch.objects.create(
            source="excel",
            period_start=self.week_start,
            period_end=self.week_end,
            file_name="week11.xlsx",
            status="imported",
        )
        Flight.objects.create(
            batch=self.batch_in_week,
            flight_number="AF702",
            departure_date=self.week_start + timedelta(days=1),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination_abj,
            capacity_units=20,
        )
        other_batch = FlightSourceBatch.objects.create(
            source="excel",
            period_start=date(2026, 3, 23),
            period_end=date(2026, 3, 29),
            file_name="week13.xlsx",
            status="imported",
        )
        Flight.objects.create(
            batch=other_batch,
            flight_number="AF718",
            departure_date=date(2026, 3, 24),
            departure_time=time(8, 0),
            destination_iata="DKR",
            origin_iata="CDG",
            routing="CDG-DKR",
            route_pos=1,
            destination=self.destination_dkr,
            capacity_units=12,
        )

    def _create_shipment(self, *, reference, ready_at, destination, status):
        shipment = Shipment.objects.create(
            reference=reference,
            status=status,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            destination=destination,
            destination_address="Airport road",
            destination_country=destination.country,
            ready_at=ready_at,
            created_by=self.planner,
        )
        warehouse = Warehouse.objects.create(name=f"WH {reference}", code=reference[-3:])
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="01",
        )
        category = ProductCategory.objects.create(name=f"Medical {reference}")
        product = Product.objects.create(
            name=f"Wheelchair {reference}",
            category=category,
            default_location=location,
        )
        lot = ProductLot.objects.create(
            product=product,
            location=location,
            quantity_on_hand=10,
        )
        carton = Carton.objects.create(
            code=f"CARTON-{reference}",
            shipment=shipment,
            current_location=location,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=lot,
            quantity=3,
        )
        ShipmentUnitEquivalenceRule.objects.create(
            label=f"Medical x2 {reference}",
            category=category,
            units_per_item=2,
            priority=1,
        )
        return shipment

    def test_build_planning_recipe_export_selects_only_week_scope(self):
        export = build_planning_recipe_export(
            week_start=self.week_start,
            week_end=self.week_end,
        )

        self.assertEqual(export.selection["week_start"], "2026-03-09")
        self.assertEqual(export.selection["week_end"], "2026-03-15")
        self.assertEqual(export.selection["parameter_set_id"], self.parameter_set.pk)
        self.assertEqual(export.summary["flights"], 1)
        self.assertEqual(export.summary["shipments"], 1)
        self.assertEqual(export.summary["volunteers"], 1)
        self.assertEqual(export.summary["destinations"], 1)
        self.assertEqual(export.summary["flight_batches"], 1)
        self.assertEqual(
            [item["reference"] for item in export.fixtures["shipments"]],
            [self.shipment_in_week.reference],
        )
        self.assertEqual(
            [item["flight_number"] for item in export.fixtures["flights"]],
            ["AF702"],
        )

    def test_build_planning_recipe_export_excludes_unrelated_history(self):
        export = build_planning_recipe_export(
            week_start=self.week_start,
            week_end=self.week_end,
        )

        self.assertNotIn("planning_versions", export.fixtures)
        self.assertEqual(len(export.fixtures["planning_parameter_sets"]), 1)
        self.assertEqual(len(export.fixtures["planning_destination_rules"]), 1)
        self.assertEqual(export.fixtures["destinations"][0]["iata_code"], "ABJ")

    def test_recipe_export_pseudonymizes_volunteers_stably(self):
        export = build_planning_recipe_export(
            week_start=self.week_start,
            week_end=self.week_end,
        )

        volunteer_payload = export.fixtures["volunteer_profiles"][0]
        shipment_payload = export.fixtures["shipments"][0]
        expected_shipper_alias = export.alias_map["contact"][self.shipper_contact.pk]
        expected_portal_email = export.fixtures["association_portal_contacts"][0]["email"]

        self.assertTrue(volunteer_payload["display_name"].startswith("VOL-"))
        self.assertTrue(volunteer_payload["email"].endswith("@example.invalid"))
        self.assertEqual(
            shipment_payload["shipper_reference"]["contact_name"], expected_shipper_alias
        )
        self.assertEqual(
            shipment_payload["shipper_reference"]["notification_emails"],
            [expected_portal_email],
        )
        self.assertEqual(
            export.alias_map["volunteer"][self.volunteer.pk],
            build_planning_recipe_export(
                week_start=self.week_start,
                week_end=self.week_end,
            ).alias_map["volunteer"][self.volunteer.pk],
        )

    def test_planning_recipe_export_command_writes_json_file(self):
        stdout = StringIO()

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "planning_recipe.json"
            call_command(
                "planning_recipe_export",
                week_start=self.week_start.isoformat(),
                week_end=self.week_end.isoformat(),
                output=str(output_path),
                stdout=stdout,
            )

            payload = json.loads(output_path.read_text())

        self.assertEqual(payload["selection"]["week_start"], "2026-03-09")
        self.assertEqual(payload["summary"]["flights"], 1)
        self.assertEqual(payload["summary"]["shipments"], 1)
        self.assertIn("wrote", stdout.getvalue().lower())
