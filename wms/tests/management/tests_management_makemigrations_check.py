import subprocess
import sys

from django.conf import settings
from django.test import TestCase


class MakemigrationsCheckTests(TestCase):
    def test_makemigrations_check_dry_run_reports_no_changes(self):
        result = subprocess.run(
            [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            self.fail(
                "makemigrations --check --dry-run reported pending model changes.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
