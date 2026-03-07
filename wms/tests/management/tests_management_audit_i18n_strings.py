from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class AuditI18nStringsCommandTests(TestCase):
    def test_audit_i18n_strings_reports_unwrapped_french_literals(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_i18n_strings", path="templates/portal/login.html", stdout=out)

    def test_audit_i18n_strings_reports_the_flagged_path(self):
        out = StringIO()

        with self.assertRaisesMessage(CommandError, "templates/portal/login.html"):
            call_command("audit_i18n_strings", path="templates/portal/login.html", stdout=out)

        self.assertIn("templates/portal/login.html", out.getvalue())
