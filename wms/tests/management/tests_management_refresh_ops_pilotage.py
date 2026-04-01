from datetime import date
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase


class RefreshOpsPilotageCommandTests(TestCase):
    @mock.patch("wms.management.commands.refresh_ops_pilotage.call_command")
    def test_refresh_ops_pilotage_runs_snapshot_and_escalation_pipeline(self, call_command_mock):
        out = StringIO()

        call_command("refresh_ops_pilotage", snapshot_date="2026-04-01", stdout=out)

        self.assertEqual(
            call_command_mock.call_args_list,
            [
                mock.call(
                    "capture_ops_pilotage_snapshot",
                    snapshot_date=date(2026, 4, 1).isoformat(),
                    stdout=mock.ANY,
                ),
                mock.call("evaluate_ops_escalations", stdout=mock.ANY),
            ],
        )
        self.assertIn("Refreshed ops pilotage", out.getvalue())
