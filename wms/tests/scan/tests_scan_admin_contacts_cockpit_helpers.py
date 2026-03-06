from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from contacts.models import Contact, ContactType
from wms.scan_admin_contacts_cockpit import (
    _find_similar_organizations,
    _format_duplicate_message,
    _is_fuzzy_match,
    _normalize_match_value,
    _normalize_role,
    _resolve_active_organization,
    _to_int,
    _validation_message,
    parse_cockpit_filters,
)


class ScanAdminContactsCockpitHelperPureTests(SimpleTestCase):
    def test_parse_cockpit_filters_sanitizes_invalid_inputs(self):
        filters = parse_cockpit_filters(role="invalid", shipper_org_id="abc")
        self.assertEqual(filters, {"role": "", "shipper_org_id": ""})

    def test_to_int_returns_none_for_invalid_values(self):
        self.assertIsNone(_to_int("x"))
        self.assertIsNone(_to_int(None))

    def test_normalize_role_returns_empty_for_unknown_role(self):
        self.assertEqual(_normalize_role("unknown"), "")

    def test_validation_message_uses_messages_fallback(self):
        message = _validation_message(ValidationError("fallback error"))
        self.assertEqual(message, "fallback error")

    def test_normalize_match_value_returns_empty_for_blank_input(self):
        self.assertEqual(_normalize_match_value("   "), "")

    def test_is_fuzzy_match_handles_empty_and_exact_values(self):
        self.assertFalse(_is_fuzzy_match(source="", candidate="abc"))
        self.assertTrue(_is_fuzzy_match(source="aviation", candidate="aviation"))

    def test_format_duplicate_message_handles_empty_and_blank_labels(self):
        self.assertEqual(_format_duplicate_message(prefix="Dup", items=[]), "")
        self.assertEqual(
            _format_duplicate_message(
                prefix="Dup",
                items=[SimpleNamespace(name="   ")],
            ),
            "Dup",
        )

    def test_resolve_active_organization_returns_none_for_invalid_identifier(self):
        self.assertIsNone(_resolve_active_organization("not-an-id"))


class ScanAdminContactsCockpitHelperDbTests(TestCase):
    def test_find_similar_organizations_handles_blank_name_and_limit(self):
        Contact.objects.create(
            name="Aviation Sans Frontieres",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        Contact.objects.create(
            name="Aviation Sans Frontiere Mali",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

        self.assertEqual(_find_similar_organizations(name="   "), [])
        matches = _find_similar_organizations(name="Aviation Sans Frontiere", limit=1)
        self.assertEqual(len(matches), 1)
