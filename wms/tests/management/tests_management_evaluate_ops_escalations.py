from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase


class EvaluateOpsEscalationsCommandTests(TestCase):
    @mock.patch(
        "wms.management.commands.evaluate_ops_escalations.sync_ops_escalations",
        return_value={"open_count": 3, "resolved_count": 1},
    )
    def test_evaluate_ops_escalations_reports_summary(self, sync_ops_escalations_mock):
        out = StringIO()

        call_command("evaluate_ops_escalations", stdout=out)

        sync_ops_escalations_mock.assert_called_once()
        self.assertIn("open=3, resolved=1", out.getvalue())
