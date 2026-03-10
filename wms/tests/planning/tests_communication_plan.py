from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    CommunicationChannel,
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from wms.planning.communication_plan import build_version_communication_plan


class PlanningCommunicationPlanTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="communication-planner",
            email="communication@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )
        self.shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            shipper_name="Association A",
            destination_iata="RUN",
            carton_count=3,
            equivalent_units=3,
        )
        self.alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        self.bob = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
        )
        self.flight_1 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF652",
            departure_date="2026-03-10",
            destination_iata="RUN",
            payload={"departure_time": "18:20"},
        )
        self.flight_2 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="RUN",
            payload={"departure_time": "19:10"},
        )

    def make_version(self, *, based_on=None, status=PlanningVersionStatus.PUBLISHED):
        return PlanningVersion.objects.create(
            run=self.run,
            based_on=based_on,
            status=status,
            created_by=self.user,
        )

    def add_assignment(
        self,
        version,
        *,
        volunteer,
        flight,
        cartons=3,
        shipment=None,
        sequence=1,
    ):
        return PlanningAssignment.objects.create(
            version=version,
            shipment_snapshot=shipment or self.shipment,
            volunteer_snapshot=volunteer,
            flight_snapshot=flight,
            assigned_carton_count=cartons,
            source=PlanningAssignmentSource.SOLVER,
            sequence=sequence,
        )

    def test_build_version_communication_plan_marks_first_publication_as_new(self):
        version = self.make_version()
        self.add_assignment(version, volunteer=self.alice, flight=self.flight_1)

        plan = build_version_communication_plan(version)

        self.assertEqual(len(plan.items), 1)
        item = plan.items[0]
        self.assertEqual(item.change_status, "new")
        self.assertEqual(item.recipient_label, "Alice")
        self.assertEqual(item.channel, CommunicationChannel.EMAIL)
        self.assertEqual(len(item.current_assignments), 1)
        self.assertEqual(item.previous_assignments, [])

    def test_build_version_communication_plan_marks_removed_recipient_as_cancelled(self):
        version_1 = self.make_version()
        self.add_assignment(version_1, volunteer=self.alice, flight=self.flight_1)
        version_2 = self.make_version(based_on=version_1)

        plan = build_version_communication_plan(version_2)

        self.assertEqual(len(plan.items), 1)
        item = plan.items[0]
        self.assertEqual(item.change_status, "cancelled")
        self.assertEqual(item.recipient_label, "Alice")
        self.assertEqual(item.current_assignments, [])
        self.assertEqual(len(item.previous_assignments), 1)

    def test_build_version_communication_plan_marks_unchanged_recipient(self):
        version_1 = self.make_version()
        self.add_assignment(version_1, volunteer=self.alice, flight=self.flight_1)
        version_2 = self.make_version(based_on=version_1)
        self.add_assignment(version_2, volunteer=self.alice, flight=self.flight_1)

        plan = build_version_communication_plan(version_2)

        self.assertEqual(len(plan.items), 1)
        item = plan.items[0]
        self.assertEqual(item.change_status, "unchanged")
        self.assertEqual(item.recipient_label, "Alice")

    def test_build_version_communication_plan_marks_changed_recipient(self):
        version_1 = self.make_version()
        self.add_assignment(version_1, volunteer=self.alice, flight=self.flight_1)
        version_2 = self.make_version(based_on=version_1)
        self.add_assignment(version_2, volunteer=self.alice, flight=self.flight_2)

        plan = build_version_communication_plan(version_2)

        self.assertEqual(len(plan.items), 1)
        item = plan.items[0]
        self.assertEqual(item.change_status, "changed")
        self.assertEqual(item.recipient_label, "Alice")

    def test_build_version_communication_plan_aggregates_assignments_per_recipient(self):
        second_shipment = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-002",
            shipper_name="Association B",
            destination_iata="ABJ",
            carton_count=2,
            equivalent_units=2,
        )
        version = self.make_version()
        self.add_assignment(
            version,
            volunteer=self.alice,
            flight=self.flight_1,
            shipment=self.shipment,
            sequence=1,
        )
        self.add_assignment(
            version,
            volunteer=self.alice,
            flight=self.flight_2,
            shipment=second_shipment,
            cartons=2,
            sequence=2,
        )

        plan = build_version_communication_plan(version)

        self.assertEqual(len(plan.items), 1)
        item = plan.items[0]
        self.assertEqual(item.change_status, "new")
        self.assertEqual(len(item.current_assignments), 2)
