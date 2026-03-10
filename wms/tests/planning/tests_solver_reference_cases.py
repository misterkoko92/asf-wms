from django.test import TestCase

from wms.planning.solver import solve_run
from wms.tests.planning.reference_cases import load_reference_case


def compute_assignment_diff(*, expected, actual):
    missing = [assignment for assignment in expected if assignment not in actual]
    extra = [assignment for assignment in actual if assignment not in expected]
    return missing, extra


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

        missing, extra = compute_assignment_diff(
            expected=case.expected_assignments,
            actual=assignments,
        )
        self.assertEqual(
            assignments,
            case.expected_assignments,
            msg=f"missing={missing} extra={extra} solver_result={case.run.solver_result}",
        )
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

    def test_reference_case_legacy_session_s10_2026_matches_expected_assignments(self):
        self._assert_reference_case("legacy_session_s10_2026")

    def test_reference_case_legacy_session_s11_2026_matches_expected_assignments(self):
        self._assert_reference_case("legacy_session_s11_2026")

    def test_compute_assignment_diff_lists_missing_and_extra_assignments(self):
        missing, extra = compute_assignment_diff(expected=[("A", "AF1", "X")], actual=[])

        self.assertEqual(missing, [("A", "AF1", "X")])
        self.assertEqual(extra, [])
