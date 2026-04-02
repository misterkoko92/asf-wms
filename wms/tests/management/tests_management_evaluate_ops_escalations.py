from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase


class EvaluateOpsEscalationsCommandTests(TestCase):
    @mock.patch(
        "wms.management.commands.evaluate_ops_escalations.run_evaluate_ops_escalations_job",
        return_value={"open_count": 3, "resolved_count": 1},
    )
    def test_evaluate_ops_escalations_reports_summary(self, evaluate_job_mock):
        out = StringIO()

        call_command("evaluate_ops_escalations", stdout=out)

        evaluate_job_mock.assert_called_once()
        self.assertIn("open=3, resolved=1", out.getvalue())
