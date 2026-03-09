from django.test import TestCase

from wms.planning.solver import solve_run
from wms.tests.planning.reference_cases import load_reference_case


class SolverReferenceCaseTests(TestCase):
    def _assert_reference_case(self, case_name: str):
        case = load_reference_case(case_name)
        version = solve_run(case.run)
        case.run.refresh_from_db()

        assignments = sorted(
            version.assignments.values_list(
                "shipment_snapshot__shipment_reference",
                "flight_snapshot__flight_number",
                "volunteer_snapshot__volunteer_label",
            )
        )

        self.assertEqual(assignments, case.expected_assignments)
        for key, value in case.expected_result.items():
            self.assertEqual(case.run.solver_result[key], value)

    def test_reference_case_nominal_week_matches_expected_assignments(self):
        self._assert_reference_case("nominal_week")

    def test_reference_case_legacy_multistop_first_stop_matches_expected_assignments(self):
        self._assert_reference_case("legacy_multistop_first_stop")

    def test_reference_case_legacy_multistop_first_stop_without_route_pos_matches_expected_assignments(
        self,
    ):
        self._assert_reference_case("legacy_multistop_first_stop_without_route_pos")

    def test_reference_case_legacy_multistop_second_stop_without_conflict_matches_expected_assignments(
        self,
    ):
        self._assert_reference_case("legacy_multistop_second_stop_without_conflict")

    def test_reference_case_legacy_no_benevole_compatible_matches_expected_result(self):
        self._assert_reference_case("legacy_no_benevole_compatible")

    def test_reference_case_legacy_session_s11_2026_matches_expected_assignments(self):
        self._assert_reference_case("legacy_session_s11_2026")
