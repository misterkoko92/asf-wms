from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.utils import ProgrammingError
from django.test import RequestFactory, TestCase

from contacts.models import Contact, ContactType
from wms.context_processors import _normalize_font_name, _resolve_design_tokens, admin_notifications
from wms.faq_changelog import build_scan_faq_change_log_entries
from wms.models import (
    Destination,
    Order,
    OrderReviewStatus,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
)
from wms.view_permissions import ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT


class ContextProcessorsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = get_user_model().objects.create_user(
            username="context-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="context-admin",
            email="context-admin@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        validator_group, _ = Group.objects.get_or_create(
            name=ACCOUNT_REQUEST_VALIDATION_GROUP_DEFAULT
        )
        validator_group.user_set.add(self.superuser)
        self.correspondent = Contact.objects.create(
            name="Correspondant Pending",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.organization = Contact.objects.create(
            name="Association Pending",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _request_for(self, user):
        request = self.factory.get("/scan/stock/")
        request.user = user
        return request

    def test_admin_notifications_returns_empty_without_pending_items(self):
        notifications = admin_notifications(self._request_for(self.staff_user))

        self.assertEqual(notifications, {})

    def test_normalize_font_name_returns_fallback_for_blank_values(self):
        self.assertEqual(_normalize_font_name("", "DM Sans"), "DM Sans")
        self.assertEqual(_normalize_font_name(None, "Nunito Sans"), "Nunito Sans")

    def test_resolve_design_tokens_returns_defaults_when_runtime_is_unavailable(self):
        with mock.patch(
            "wms.context_processors.get_runtime_settings_instance",
            side_effect=ProgrammingError("table missing"),
        ):
            tokens = _resolve_design_tokens()

        self.assertEqual(tokens["font_h1"], "DM Sans")
        self.assertEqual(tokens["font_body"], "Nunito Sans")
        self.assertIn("density_factor", tokens)

    def test_admin_notifications_aggregates_pending_actions_for_superuser(self):
        Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association attente",
            destination_address="3 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.PENDING,
        )
        PublicAccountRequest.objects.create(
            association_name="Compte attente",
            email="pending@example.com",
            address_line1="1 rue du Test",
            status=PublicAccountRequestStatus.PENDING,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=self.organization,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
        )

        notifications = admin_notifications(self._request_for(self.superuser))

        self.assertEqual(notifications["admin_pending_orders_to_review"], 1)
        self.assertEqual(notifications["admin_pending_account_requests"], 1)
        self.assertEqual(notifications["admin_pending_recipient_validations"], 1)
        self.assertEqual(notifications["scan_pending_actions_total"], 3)
        self.assertEqual(
            [item["key"] for item in notifications["scan_pending_action_items"]],
            ["orders", "account_requests", "recipient_validations"],
        )
        self.assertEqual(
            [item["url"] for item in notifications["scan_pending_action_items"]],
            [
                "/scan/orders-view/",
                "/scan/account-validations/",
                "/scan/contacts/validations/recipients/",
            ],
        )

    def test_build_scan_faq_change_log_entries_formats_labels_and_sorts(self):
        with mock.patch(
            "wms.faq_changelog.SCAN_FAQ_CHANGE_LOG_ENTRIES",
            [
                {
                    "date": date(2026, 4, 20),
                    "pr_number": None,
                    "summary": "Ancienne entrée sans PR",
                },
                {
                    "date": date(2026, 4, 24),
                    "pr_number": 179,
                    "summary": "Entrée récente",
                },
            ],
        ):
            entries = build_scan_faq_change_log_entries()

        self.assertEqual(
            [entry["summary"] for entry in entries],
            ["Entrée récente", "Ancienne entrée sans PR"],
        )
        self.assertEqual(entries[0]["pr_label"], "PR #179")
        self.assertEqual(entries[1]["pr_label"], "PR à renseigner avant merge")
