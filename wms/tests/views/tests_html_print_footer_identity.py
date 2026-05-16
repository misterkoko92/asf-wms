import html
import re

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from wms.config import get_installation_config
from wms.documents import build_org_context
from wms.print_context import build_print_footer_context

PRINT_BASE_TEMPLATES = (
    "print/base_document.html",
    "print/base_a5.html",
)

FOOTER_SETTING_CASES = (
    (
        "PRINT_HTML_FOOTER_PUBLIC_CONTACT_LINE",
        "html_footer_public_contact_line",
        "PR20 public contact footer override",
    ),
    (
        "PRINT_HTML_FOOTER_HEADQUARTERS_LINE",
        "html_footer_headquarters_line",
        "PR20 headquarters footer override",
    ),
    (
        "PRINT_HTML_FOOTER_WAREHOUSE_LINE",
        "html_footer_warehouse_line",
        "PR20 warehouse footer override",
    ),
    (
        "PRINT_HTML_FOOTER_LEGAL_NOTICE_LINE",
        "html_footer_legal_notice_line",
        "PR20 legal notice footer override",
    ),
)

ORG_NAME_PROBE = "TEST ORG FULL NAME PR17"
ORG_CONTACT_PROBE = "TEST ORG CONTACT PR17"
ORG_ADDRESS_PROBE = "TEST ORG ADDRESS PR17"

_FOOTER_RE = re.compile(
    r'<footer class="print-footer">\s*(?P<footer>.*?)\s*</footer>',
    re.DOTALL,
)
_FOOTER_LINE_RE = re.compile(r"<div>(?P<line>.*?)</div>", re.DOTALL)


def _configured_footer_lines():
    footer = get_installation_config().print
    return (
        footer.html_footer_public_contact_line,
        footer.html_footer_headquarters_line,
        footer.html_footer_warehouse_line,
        footer.html_footer_legal_notice_line,
    )


class HtmlPrintFooterIdentityTests(SimpleTestCase):
    def _render_footer_lines(self, template_name, context=None):
        rendered = render_to_string(
            template_name,
            {
                **build_print_footer_context(),
                **(context or {}),
            },
        )
        footer_match = _FOOTER_RE.search(rendered)
        if footer_match is None:
            return ()
        return tuple(
            html.unescape(line).strip()
            for line in _FOOTER_LINE_RE.findall(footer_match.group("footer"))
        )

    def test_base_document_renders_configured_footer_lines(self):
        self.assertEqual(
            self._render_footer_lines("print/base_document.html"),
            _configured_footer_lines(),
        )

    def test_base_a5_renders_configured_footer_lines(self):
        self.assertEqual(
            self._render_footer_lines("print/base_a5.html"),
            _configured_footer_lines(),
        )

    def test_hide_footer_removes_configured_footer_lines(self):
        for template_name in PRINT_BASE_TEMPLATES:
            with self.subTest(template_name=template_name):
                self.assertEqual(
                    self._render_footer_lines(template_name, {"hide_footer": True}),
                    (),
                )

    @override_settings(
        ORG_CONTACT=ORG_CONTACT_PROBE,
        ORG_ADDRESS=ORG_ADDRESS_PROBE,
    )
    def test_org_contact_and_address_overrides_do_not_change_footer_contract(self):
        context = build_org_context()
        self.assertEqual(context["org_contact"], ORG_CONTACT_PROBE)
        self.assertEqual(context["org_address"], ORG_ADDRESS_PROBE)

        for template_name in PRINT_BASE_TEMPLATES:
            with self.subTest(template_name=template_name):
                footer_lines = self._render_footer_lines(template_name, context)
                footer_text = "\n".join(footer_lines)
                self.assertEqual(footer_lines, _configured_footer_lines())
                self.assertNotIn(ORG_CONTACT_PROBE, footer_text)
                self.assertNotIn(ORG_ADDRESS_PROBE, footer_text)

    @override_settings(ORG_NAME=ORG_NAME_PROBE)
    def test_org_name_feeds_context_but_not_footer_contract(self):
        context = build_org_context()
        self.assertEqual(context["org_name"], ORG_NAME_PROBE)

        for template_name in PRINT_BASE_TEMPLATES:
            with self.subTest(template_name=template_name):
                footer_lines = self._render_footer_lines(template_name, context)
                footer_text = "\n".join(footer_lines)
                self.assertEqual(footer_lines, _configured_footer_lines())
                self.assertNotIn(ORG_NAME_PROBE, footer_text)

    def test_print_footer_settings_override_each_footer_line_in_base_templates(self):
        for setting_name, field_name, override_value in FOOTER_SETTING_CASES:
            with self.subTest(setting_name=setting_name):
                with override_settings(**{setting_name: override_value}):
                    expected_lines = _configured_footer_lines()
                    self.assertIn(override_value, expected_lines)
                    self.assertEqual(
                        getattr(get_installation_config().print, field_name),
                        override_value,
                    )
                    for template_name in PRINT_BASE_TEMPLATES:
                        with self.subTest(template_name=template_name):
                            self.assertEqual(
                                self._render_footer_lines(template_name),
                                expected_lines,
                            )
