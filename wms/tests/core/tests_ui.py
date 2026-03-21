import os
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Location,
    Product,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    Warehouse,
)

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional test dependency
    sync_playwright = None


@unittest.skipUnless(os.getenv("RUN_UI_TESTS") == "1", "UI tests disabled")
@unittest.skipIf(sync_playwright is None, "Playwright not installed")
class ScanUiTests(StaticLiveServerTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ui-user",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        warehouse = Warehouse.objects.create(name="UI WH", code="UI")
        location = Location.objects.create(warehouse=warehouse, zone="A", aisle="01", shelf="001")
        Product.objects.create(
            sku="UI-001",
            name="UI Product",
            weight_g=100,
            volume_cm3=100,
            default_location=location,
            qr_code_image="qr_codes/test.png",
        )

    def _new_context(self, browser, init_script=None):
        context = browser.new_context()
        if init_script:
            context.add_init_script(init_script)
        context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": self.session_cookie.value,
                    "url": self.live_server_url,
                }
            ]
        )
        return context

    @unittest.skipUnless(
        os.getenv("RUN_UI_TESTS_MEDIA") == "1",
        "MediaDevices fallback test disabled",
    )
    def test_scan_shows_alert_when_media_devices_missing(self):
        init_script = (
            "Object.defineProperty(navigator, 'mediaDevices', "
            "{ value: undefined, configurable: true });"
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser, init_script=init_script)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_stock_update')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector(".scan-scan-btn")
            with page.expect_event("dialog") as dialog_info:
                page.dispatch_event(".scan-scan-btn", "click")
            dialog = dialog_info.value
            self.assertIn("Scan camera non supporte", dialog.message)
            dialog.dismiss()
            context.close()
            browser.close()

    def test_scan_sets_status_on_camera_denied(self):
        init_script = (
            "Object.defineProperty(navigator, 'mediaDevices', {"
            "  value: { getUserMedia: () => Promise.reject(new Error('denied')) },"
            "  configurable: true"
            "});"
        )
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser, init_script=init_script)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_stock_update')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector(".scan-scan-btn")
            page.dispatch_event(".scan-scan-btn", "click")
            page.wait_for_function(
                "document.getElementById('scan-status').textContent"
                ".includes('Accès caméra refusé.')"
            )
            status_text = page.locator("#scan-status").inner_text()
            self.assertIn("Accès caméra refusé.", status_text)
            context.close()
            browser.close()

    def test_scan_shipment_create_hides_unbound_recipients_when_shipment_links_apply(self):
        shipper = Contact.objects.create(
            name="UI Shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_person = Contact.objects.create(
            name="Alice Shipper",
            first_name="Alice",
            last_name="Shipper",
            contact_type=ContactType.PERSON,
            organization=shipper,
            is_active=True,
        )
        recipient_allowed = Contact.objects.create(
            name="UI Recipient Allowed",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_allowed_person = Contact.objects.create(
            name="Leontine Rahazania",
            first_name="Leontine",
            last_name="Rahazania",
            contact_type=ContactType.PERSON,
            organization=recipient_allowed,
            is_active=True,
        )
        recipient_blocked = Contact.objects.create(
            name="UI Recipient Blocked",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_blocked_person = Contact.objects.create(
            name="Marie Blocked",
            first_name="Marie",
            last_name="Blocked",
            contact_type=ContactType.PERSON,
            organization=recipient_blocked,
            is_active=True,
        )
        destination = Destination.objects.create(
            city="Antananarivo",
            iata_code="TNR-UI",
            country="Madagascar",
            correspondent_contact=recipient_allowed_person,
            is_active=True,
        )

        shipper_model = ShipmentShipper.objects.create(
            organization=shipper,
            default_contact=shipper_person,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_allowed_model = ShipmentRecipientOrganization.objects.create(
            organization=recipient_allowed,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )
        recipient_blocked_model = ShipmentRecipientOrganization.objects.create(
            organization=recipient_blocked,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        allowed_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_allowed_model,
            contact=recipient_allowed_person,
            is_active=True,
        )
        ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_blocked_model,
            contact=recipient_blocked_person,
            is_active=True,
        )
        allowed_link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper_model,
            recipient_organization=recipient_allowed_model,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=allowed_link,
            recipient_contact=allowed_recipient_contact,
            is_default=True,
            is_active=True,
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_shipment_create')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h2")
            page.locator("#id_destination").select_option(str(destination.id))
            page.locator("#id_shipper_contact").select_option(str(shipper.id))
            page.wait_for_function(
                "(allowedId) => !!document.querySelector("
                ' `#id_recipient_contact option[value="${allowedId}"]`'
                ")",
                arg=str(recipient_allowed_person.id),
            )

            self.assertEqual(
                page.locator(
                    f'#id_recipient_contact option[value="{recipient_allowed_person.id}"]'
                ).count(),
                1,
            )
            self.assertEqual(
                page.locator(
                    f'#id_recipient_contact option[value="{recipient_blocked_person.id}"]'
                ).count(),
                0,
            )
            context.close()
            browser.close()
