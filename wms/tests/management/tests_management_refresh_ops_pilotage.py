from datetime import date
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
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

    def test_refresh_ops_pilotage_rejects_invalid_snapshot_date(self):
        with self.assertRaises(CommandError) as error:
            call_command("refresh_ops_pilotage", snapshot_date="2026-99-99")

        self.assertIn("snapshot-date", str(error.exception))

    @mock.patch("wms.management.commands.refresh_ops_pilotage.timezone.localdate")
    @mock.patch("wms.management.commands.refresh_ops_pilotage.call_command")
    def test_refresh_ops_pilotage_uses_localdate_when_snapshot_date_is_missing(
        self,
        call_command_mock,
        localdate_mock,
    ):
        out = StringIO()
        localdate_mock.return_value = date(2026, 4, 2)

        call_command("refresh_ops_pilotage", stdout=out)

        self.assertEqual(
            call_command_mock.call_args_list,
            [
                mock.call(
                    "capture_ops_pilotage_snapshot",
                    snapshot_date="2026-04-02",
                    stdout=mock.ANY,
                ),
                mock.call("evaluate_ops_escalations", stdout=mock.ANY),
            ],
        )
        self.assertIn("2026-04-02", out.getvalue())
