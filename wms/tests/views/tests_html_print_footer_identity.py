import html
import re

from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from wms.documents import build_org_context

FOOTER_LINES = (
    "https://aviation-sans-frontieres.org/messmed // " "messmed@aviation-sans-frontières-fr.org",
    "Siège: Bat 293, Porte 1150, Orly Fret 768 - 94398 Orly Aérogare Cedex - "
    "Tel: (33) 1 49 75 74 36",
    "Magasin: Bat. 7200, Porte 2D520, rue de la Remise - 95700 ROISSY en France - "
    "Tél: (33) 1 74 25 03 22",
    "Association reconnue d'utilité publique par décret du 12 novembre 1993",
)

PRINT_BASE_TEMPLATES = (
    "print/base_document.html",
    "print/base_a5.html",
)

ORG_NAME_PROBE = "TEST ORG FULL NAME PR17"
ORG_CONTACT_PROBE = "TEST ORG CONTACT PR17"
ORG_ADDRESS_PROBE = "TEST ORG ADDRESS PR17"

_FOOTER_RE = re.compile(
    r'<footer class="print-footer">\s*(?P<footer>.*?)\s*</footer>',
    re.DOTALL,
)
_FOOTER_LINE_RE = re.compile(r"<div>(?P<line>.*?)</div>", re.DOTALL)


class HtmlPrintFooterIdentityTests(SimpleTestCase):
    def _render_footer_lines(self, template_name, context=None):
        rendered = render_to_string(template_name, context or {})
        footer_match = _FOOTER_RE.search(rendered)
        if footer_match is None:
            return ()
        return tuple(
            html.unescape(line).strip()
            for line in _FOOTER_LINE_RE.findall(footer_match.group("footer"))
        )

    def test_base_document_renders_current_hardcoded_footer_lines(self):
        self.assertEqual(
            self._render_footer_lines("print/base_document.html"),
            FOOTER_LINES,
        )

    def test_base_a5_renders_current_hardcoded_footer_lines(self):
        self.assertEqual(
            self._render_footer_lines("print/base_a5.html"),
            FOOTER_LINES,
        )

    def test_hide_footer_removes_current_hardcoded_footer_lines(self):
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
                self.assertEqual(footer_lines, FOOTER_LINES)
                self.assertNotIn(ORG_CONTACT_PROBE, footer_text)
                self.assertNotIn(ORG_ADDRESS_PROBE, footer_text)

    @override_settings(ORG_NAME=ORG_NAME_PROBE)
    def test_org_name_feeds_context_but_not_hardcoded_footer_contract(self):
        context = build_org_context()
        self.assertEqual(context["org_name"], ORG_NAME_PROBE)

        for template_name in PRINT_BASE_TEMPLATES:
            with self.subTest(template_name=template_name):
                footer_lines = self._render_footer_lines(template_name, context)
                footer_text = "\n".join(footer_lines)
                self.assertEqual(footer_lines, FOOTER_LINES)
                self.assertNotIn(ORG_NAME_PROBE, footer_text)
