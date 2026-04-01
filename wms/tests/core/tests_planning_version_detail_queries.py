from django.contrib.auth import get_user_model
from django.test import TestCase

from wms.application.planning.version_detail_queries import (
    build_planning_version_detail_payload,
)
from wms.models import PlanningParameterSet, PlanningRun, PlanningRunStatus, PlanningVersion


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
