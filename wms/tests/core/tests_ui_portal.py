import os
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    PlanningParameterSet,
    PortalAccessGrant,
    PortalAccessRole,
    Product,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
    VolunteerProfile,
)
from wms.portal_access import ACTIVE_PORTAL_SCOPE_SESSION_KEY, PORTAL_SCOPE_SOURCE_GRANT
from wms.portal_recipient_sync import sync_association_recipient_to_contact

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional test dependency
    sync_playwright = None


@unittest.skipUnless(os.getenv("RUN_UI_TESTS") == "1", "UI tests disabled")
@unittest.skipIf(sync_playwright is None, "Playwright not installed")
class PortalUiTests(StaticLiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.shipper_user = get_user_model().objects.create_user(
            username="ui-portal-shipper",
            password="pass1234",  # pragma: allowlist secret
            email="ui-portal-shipper@example.com",
        )
        association_contact = Contact.objects.create(
            name="Association UI Portal",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association-ui-portal@example.com",
        )
        ContactAddress.objects.create(
            contact=association_contact,
            address_line1="1 Rue Test",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.shipper_user,
            contact=association_contact,
            must_change_password=False,
        )
        correspondent = Contact.objects.create(
            name="Correspondant UI",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako UI",
            iata_code="BUI",
            country="Mali",
            correspondent_contact=correspondent,
            is_active=True,
        )
        self.delivery_recipient = AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=self.destination,
            name="Destinataire UI",
            structure_name="Structure UI",
            address_line1="2 Rue Livraison",
            city="Bamako UI",
            country="Mali",
            is_delivery_contact=True,
            is_active=True,
        )
        sync_association_recipient_to_contact(self.delivery_recipient)
        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=self.delivery_recipient.synced_contact,
            destination=self.destination,
        )
        recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
        recipient_organization.save(update_fields=["validation_status"])
        self.recipient_organization = recipient_organization

        self.recipient_scope_user = get_user_model().objects.create_user(
            username="ui-portal-recipient",
            password="pass1234",  # pragma: allowlist secret
            email="ui-portal-recipient@example.com",
        )
        self.recipient_grant = PortalAccessGrant.objects.create(
            user=self.recipient_scope_user,
            role=PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=recipient_organization,
        )

        Product.objects.create(
            sku="UI-PORTAL-001",
            name="Produit UI Portail",
            brand="ASF",
            qr_code_image="qr_codes/ui_portal_001.png",
        )

        self.staff_user = get_user_model().objects.create_user(
            username="ui-planning-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        PlanningParameterSet.objects.create(
            name="UI Planning Param",
            is_current=True,
        )

        self.volunteer_user = get_user_model().objects.create_user(
            username="ui-volunteer",
            password="pass1234",  # pragma: allowlist secret
            email="ui-volunteer@example.com",
        )
        VolunteerProfile.objects.create(
            user=self.volunteer_user,
            must_change_password=False,
        )

    def _login_session_cookie(self, user, *, session_updates=None):
        client = self.client_class()
        client.force_login(user)
        if session_updates:
            session = client.session
            for key, value in session_updates.items():
                session[key] = value
            session.save()
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def _new_context(self, browser, *, session_value):
        context = browser.new_context()
        context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session_value,
                    "url": self.live_server_url,
                }
            ]
        )
        return context

    def test_portal_order_create_progressive_flow_reveals_fulfillment_after_route_selection(self):
        session_value = self._login_session_cookie(self.shipper_user)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser, session_value=session_value)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('portal:portal_order_create')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("#portal-order-create-form")

            self.assertEqual(
                page.locator("#portal-order-create-fulfillment-step").get_attribute(
                    "data-portal-order-step-hidden"
                ),
                "1",
            )
            self.assertEqual(
                page.locator("#portal-order-create-review-step").get_attribute(
                    "data-portal-order-step-hidden"
                ),
                "1",
            )

            page.locator("#destination_id").select_option(str(self.destination.id))
            page.wait_for_function(
                "() => document.querySelectorAll('#recipient_id option').length > 1"
            )
            page.locator("#recipient_id").select_option(str(self.delivery_recipient.id))
            page.wait_for_function(
                "() => document.getElementById('portal-order-create-fulfillment-step')"
                ".getAttribute('data-portal-order-step-hidden') === '0'"
            )

            self.assertEqual(
                page.locator("#portal-order-create-review-step").get_attribute(
                    "data-portal-order-step-hidden"
                ),
                "0",
            )
            self.assertIn(
                "Bamako UI",
                page.locator("#portal-order-create-summary-destination").inner_text(),
            )
            self.assertIn(
                "Structure UI",
                page.locator("#portal-order-create-summary-recipient").inner_text(),
            )
            context.close()
            browser.close()

    def test_portal_recipient_profile_smoke_uses_recipient_scope_surface(self):
        session_value = self._login_session_cookie(
            self.recipient_scope_user,
            session_updates={
                ACTIVE_PORTAL_SCOPE_SESSION_KEY: {
                    "source": PORTAL_SCOPE_SOURCE_GRANT,
                    "grant_id": self.recipient_grant.id,
                }
            },
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser, session_value=session_value)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('portal:portal_recipient_profile')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("#portal-recipient-profile-form")
            self.assertIn("Portail destinataire", page.locator("#portal-masthead").inner_text())
            self.assertEqual(page.locator("#structure_name").input_value(), "Structure UI")
            self.assertIn(
                "Bamako UI (BUI)",
                page.locator("#recipient_destination_label").input_value(),
            )
            context.close()
            browser.close()

    def test_planning_run_list_smoke_keeps_shared_shell_navigation(self):
        session_value = self._login_session_cookie(self.staff_user)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser, session_value=session_value)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('planning:run_list')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("#planning-page-header")
            self.assertIn("Planning", page.locator("#planning-masthead").inner_text())
            self.assertGreater(page.locator("#scan-sidebar-nav").count(), 0)
            context.close()
            browser.close()
