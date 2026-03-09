from django.test import TestCase

from wms.planning.solver import solve_run
from wms.tests.planning.reference_cases import load_reference_case


class SolverReferenceCaseTests(TestCase):
    def test_reference_case_nominal_week_matches_expected_assignments(self):
        case = load_reference_case("nominal_week")

        version = solve_run(case.run)

        assignments = sorted(
            version.assignments.values_list(
                "shipment_snapshot__shipment_reference",
                "flight_snapshot__flight_number",
                "volunteer_snapshot__volunteer_label",
            )
        )

        self.assertEqual(assignments, case.expected_assignments)
