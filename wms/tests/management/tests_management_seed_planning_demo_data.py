from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from wms.models import (
    AssociationPortalContact,
    Flight,
    FlightSourceBatch,
    PlanningAssignment,
    PlanningDestinationRule,
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningVersion,
    PlanningVersionStatus,
    Shipment,
    VolunteerAvailability,
    VolunteerProfile,
)


class SeedPlanningDemoDataCommandTests(TestCase):
    def test_command_creates_demo_dataset(self):
        output = StringIO()

        call_command(
            "seed_planning_demo_data",
            "--scenario=test-demo",
            stdout=output,
        )

        self.assertTrue(Contact.objects.filter(name__startswith="[DEMO test-demo]").exists())
        self.assertEqual(PlanningParameterSet.objects.filter(name="DEMO test-demo").count(), 1)
        self.assertEqual(
            PlanningDestinationRule.objects.filter(parameter_set__name="DEMO test-demo").count(),
            2,
        )
        self.assertEqual(
            VolunteerProfile.objects.filter(user__email__contains="test-demo").count(),
            2,
        )
        self.assertEqual(
            VolunteerAvailability.objects.filter(
                volunteer__user__email__contains="test-demo"
            ).count(),
            3,
        )
        self.assertEqual(
            AssociationPortalContact.objects.filter(email__contains="test-demo").count(),
            2,
        )
        self.assertEqual(Shipment.objects.filter(reference__startswith="DEMO-TEST-DEMO").count(), 3)
        self.assertEqual(FlightSourceBatch.objects.filter(source="demo").count(), 1)
        self.assertEqual(Flight.objects.filter(batch__source="demo").count(), 2)
        self.assertEqual(PlanningRun.objects.count(), 1)
        self.assertIn("Scenario test-demo ready", output.getvalue())

    def test_command_can_prepare_and_solve_run(self):
        output = StringIO()

        call_command(
            "seed_planning_demo_data",
            "--scenario=smoke",
            "--solve",
            stdout=output,
        )

        run = PlanningRun.objects.get()
        version = PlanningVersion.objects.get(run=run)

        self.assertEqual(run.status, PlanningRunStatus.SOLVED)
        self.assertEqual(version.status, PlanningVersionStatus.DRAFT)
        self.assertGreaterEqual(PlanningAssignment.objects.filter(version=version).count(), 1)
        self.assertIn("solved", output.getvalue().lower())
