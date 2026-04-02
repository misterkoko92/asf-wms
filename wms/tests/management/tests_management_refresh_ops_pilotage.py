from datetime import date
from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase


class RefreshOpsPilotageCommandTests(TestCase):
    @mock.patch(
        "wms.management.commands.refresh_ops_pilotage.run_refresh_ops_pilotage_job",
        return_value={"snapshot_date": date(2026, 4, 1)},
    )
    def test_refresh_ops_pilotage_runs_snapshot_and_escalation_pipeline(self, refresh_job_mock):
        out = StringIO()

        call_command("refresh_ops_pilotage", snapshot_date="2026-04-01", stdout=out)

        refresh_job_mock.assert_called_once_with(
            snapshot_date=date(2026, 4, 1),
        )
        self.assertIn("Refreshed ops pilotage", out.getvalue())

    def test_refresh_ops_pilotage_rejects_invalid_snapshot_date(self):
        with self.assertRaises(CommandError) as error:
            call_command("refresh_ops_pilotage", snapshot_date="2026-99-99")

        self.assertIn("snapshot-date", str(error.exception))

    @mock.patch("wms.management.commands.refresh_ops_pilotage.timezone.localdate")
    @mock.patch("wms.management.commands.refresh_ops_pilotage.run_refresh_ops_pilotage_job")
    def test_refresh_ops_pilotage_uses_localdate_when_snapshot_date_is_missing(
        self,
        refresh_job_mock,
        localdate_mock,
    ):
        out = StringIO()
        localdate_mock.return_value = date(2026, 4, 2)

        call_command("refresh_ops_pilotage", stdout=out)

        refresh_job_mock.assert_called_once_with(snapshot_date=date(2026, 4, 2))
        self.assertIn("2026-04-02", out.getvalue())
