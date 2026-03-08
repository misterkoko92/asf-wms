from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.models import (
    PlanningAssignment,
    PlanningAssignmentSource,
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningShipmentSnapshot,
    PlanningVersion,
    PlanningVersionStatus,
    PlanningVolunteerSnapshot,
)
from wms.planning.versioning import clone_version, diff_versions, publish_version


class PlanningVersioningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planner@example.com",
            email="planner@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            created_by=self.user,
        )
        self.shipment_snapshot = PlanningShipmentSnapshot.objects.create(
            run=self.run,
            shipment_reference="SHP-001",
            carton_count=3,
            equivalent_units=3,
        )
        self.volunteer_alice = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Alice",
        )
        self.volunteer_bob = PlanningVolunteerSnapshot.objects.create(
            run=self.run,
            volunteer_label="Bob",
        )
        self.flight_af123 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF123",
            departure_date="2026-03-10",
            destination_iata="CDG",
        )
        self.flight_af456 = PlanningFlightSnapshot.objects.create(
            run=self.run,
            flight_number="AF456",
            departure_date="2026-03-11",
            destination_iata="NCE",
        )
        self.original = PlanningVersion.objects.create(
            run=self.run,
            status=PlanningVersionStatus.PUBLISHED,
            created_by=self.user,
        )
        PlanningAssignment.objects.create(
            version=self.original,
            shipment_snapshot=self.shipment_snapshot,
            volunteer_snapshot=self.volunteer_alice,
            flight_snapshot=self.flight_af123,
            assigned_carton_count=3,
            source=PlanningAssignmentSource.SOLVER,
            sequence=1,
        )

    def test_clone_version_creates_new_draft_with_based_on_link(self):
        clone = clone_version(
            self.original,
            created_by=self.user,
            change_reason="Maj vendredi",
        )

        self.assertEqual(clone.status, PlanningVersionStatus.DRAFT)
        self.assertEqual(clone.based_on, self.original)
        self.assertEqual(clone.change_reason, "Maj vendredi")

        copied_assignment = clone.assignments.get()
        self.assertEqual(copied_assignment.source, PlanningAssignmentSource.COPIED)
        self.assertEqual(copied_assignment.shipment_snapshot, self.shipment_snapshot)
        self.assertEqual(copied_assignment.volunteer_snapshot, self.volunteer_alice)
        self.assertEqual(copied_assignment.flight_snapshot, self.flight_af123)

    def test_publish_version_supersedes_previous_publication(self):
        draft = clone_version(
            self.original,
            created_by=self.user,
            change_reason="Maj vendredi",
        )

        publish_version(draft)

        self.original.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(self.original.status, PlanningVersionStatus.SUPERSEDED)
        self.assertEqual(draft.status, PlanningVersionStatus.PUBLISHED)
        self.assertIsNotNone(draft.published_at)

    def test_diff_versions_reports_changed_assignments(self):
        draft = clone_version(
            self.original,
            created_by=self.user,
            change_reason="Maj vendredi",
        )
        updated_assignment = draft.assignments.get()
        updated_assignment.volunteer_snapshot = self.volunteer_bob
        updated_assignment.flight_snapshot = self.flight_af456
        updated_assignment.assigned_carton_count = 5
        updated_assignment.notes = "Manual swap"
        updated_assignment.source = PlanningAssignmentSource.MANUAL
        updated_assignment.save()

        diff = diff_versions(self.original, draft)

        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])
        self.assertEqual(len(diff["changed"]), 1)
        changed = diff["changed"][0]
        self.assertEqual(changed["shipment_reference"], "SHP-001")
        self.assertEqual(changed["from"]["volunteer"], "Alice")
        self.assertEqual(changed["to"]["volunteer"], "Bob")
        self.assertEqual(changed["from"]["flight"], "AF123")
        self.assertEqual(changed["to"]["flight"], "AF456")
        self.assertEqual(changed["from"]["cartons"], 3)
        self.assertEqual(changed["to"]["cartons"], 5)
