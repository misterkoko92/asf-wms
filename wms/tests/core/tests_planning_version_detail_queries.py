from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from wms.application.planning.version_detail_queries import (
    _attach_operator_options,
    build_planning_version_detail_payload,
)
from wms.models import (
    PlanningParameterSet,
    PlanningRun,
    PlanningRunStatus,
    PlanningVersion,
    PlanningVersionStatus,
)


class PlanningVersionDetailQueriesTests(TestCase):
    def test_build_planning_version_detail_payload_exposes_dashboard_and_priorities(self):
        user = get_user_model().objects.create(username="planning-query-user")
        parameter_set = PlanningParameterSet.objects.create(
            name="Planning Query",
            is_current=True,
            created_by=user,
        )
        run = PlanningRun.objects.create(
            week_start="2026-03-09",
            week_end="2026-03-15",
            parameter_set=parameter_set,
            status=PlanningRunStatus.SOLVED,
            created_by=user,
            solver_result={"unassigned_reasons": {}},
        )
        version = PlanningVersion.objects.create(
            run=run,
            created_by=user,
        )

        payload = build_planning_version_detail_payload(version=version)

        self.assertIn("dashboard", payload)
        self.assertIn("priority_cards", payload)


class PlanningVersionDetailQueryHelpersTests(SimpleTestCase):
    @mock.patch("wms.application.planning.version_detail_queries.build_operator_option_context")
    def test_attach_operator_options_skips_rows_missing_runtime_objects(self, context_mock):
        context_mock.return_value = {"context": "ok"}
        version = SimpleNamespace(
            status=PlanningVersionStatus.DRAFT,
            assignments=SimpleNamespace(select_related=lambda *args: []),
            run=SimpleNamespace(
                shipment_snapshots=SimpleNamespace(all=lambda: []),
            ),
        )
        dashboard = {
            "planning_rows": [{"assignment_id": 1}],
            "flight_groups": [{"assignments": [{"assignment_id": 2}]}],
            "unassigned_shipments": [{"shipment_snapshot_id": 3}],
        }

        _attach_operator_options(version, dashboard)

        self.assertNotIn("editor_options", dashboard["planning_rows"][0])
        self.assertNotIn("editor_options", dashboard["flight_groups"][0]["assignments"][0])
        self.assertNotIn("editor_options", dashboard["unassigned_shipments"][0])
