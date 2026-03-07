from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from wms.management.commands.audit_i18n_strings import (
    _iter_candidate_files,
    _relative_to_project_root,
)


class AuditI18nStringsCommandTests(TestCase):
    def _write_template(self, tmp_dir: str, filename: str, content: str) -> Path:
        path = Path(tmp_dir) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_audit_i18n_strings_reports_unwrapped_french_literals(self):
        with TemporaryDirectory() as tmp_dir:
            template_path = self._write_template(
                tmp_dir,
                "audit.html",
                '<h1 class="ui-comp-title">Connexion association</h1>\n',
            )
            out = StringIO()

            with self.assertRaisesMessage(CommandError, str(template_path)):
                call_command("audit_i18n_strings", path=str(template_path), stdout=out)

            output = out.getvalue()
            self.assertIn(str(template_path), output)
            self.assertIn("Connexion association", output)

    def test_audit_i18n_strings_ignores_neutral_brand_and_placeholder_literals(self):
        with TemporaryDirectory() as tmp_dir:
            template_path = self._write_template(
                tmp_dir,
                "neutral.html",
                "\n".join(
                    [
                        '<strong class="ui-comp-title">ASF WMS</strong>',
                        '<label class="form-label">Email</label>',
                        '<input placeholder="email@domaine.org">',
                        "<div>https://aviation-sans-frontieres.org/messmed</div>",
                        (
                            "<div>https://aviation-sans-frontieres.org/messmed // "
                            "messmed@aviation-sans-frontieres-fr.org</div>"
                        ),
                    ]
                )
                + "\n",
            )
            out = StringIO()

            call_command("audit_i18n_strings", path=str(template_path), stdout=out)

            self.assertIn("Audit i18n strings: OK.", out.getvalue())

    def test_audit_i18n_strings_reports_mixed_translated_and_raw_line(self):
        with TemporaryDirectory() as tmp_dir:
            template_path = self._write_template(
                tmp_dir,
                "mixed.html",
                (
                    '<div>{% trans "Siège" %}: Bat. 7200, Porte 2D520, '
                    "rue de la Remise - 95700 ROISSY en France - "
                    '{% trans "Tél" %}: (33) 1 74 25 03 22</div>\n'
                ),
            )
            out = StringIO()

            with self.assertRaisesMessage(CommandError, str(template_path)):
                call_command("audit_i18n_strings", path=str(template_path), stdout=out)

            output = out.getvalue()
            self.assertIn(str(template_path), output)
            self.assertIn("rue de la Remise", output)

    def test_default_audit_scope_includes_active_scan_templates(self):
        candidates = {_relative_to_project_root(path) for path in _iter_candidate_files(None)}

        self.assertIn("templates/scan/admin_contacts.html", candidates)
        self.assertIn("templates/scan/print_template_list.html", candidates)
