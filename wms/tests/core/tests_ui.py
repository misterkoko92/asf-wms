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
        self.location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        Product.objects.create(
            sku="UI-001",
            name="UI Product",
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
            qr_code_image="qr_codes/test.png",
        )

    def _new_context(self, browser, init_script=None, **kwargs):
        context = browser.new_context(**kwargs)
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

    def test_scan_ui_lab_enhances_shared_number_input(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_ui_lab')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("#ui-lab-number-input-demo")
            page.wait_for_function(
                "(() => {"
                "  const input = document.getElementById('ui-lab-number-input-demo');"
                "  return !!input"
                "    && input.classList.contains('is-ui-number-input-enhanced')"
                "    && !!input.closest('.ui-number-input')"
                "    && !!input.closest('.ui-number-input').querySelector('.ui-number-input-controls');"
                "})()"
            )

            decrement = page.locator(
                '[data-ui-number-input-target="ui-lab-number-input-demo"]'
                '[data-ui-number-input-action="decrement"]'
            )
            increment = page.locator(
                '[data-ui-number-input-target="ui-lab-number-input-demo"]'
                '[data-ui-number-input-action="increment"]'
            )
            self.assertEqual(decrement.count(), 1)
            self.assertEqual(increment.count(), 1)

            decrement.click()
            page.wait_for_function(
                "() => document.getElementById('ui-lab-number-input-demo').value === '2'"
            )
            increment.click()
            page.wait_for_function(
                "() => document.getElementById('ui-lab-number-input-demo').value === '3'"
            )
            context.close()
            browser.close()

    def test_scan_pack_enhances_quantity_inputs_added_dynamically(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(browser)
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_pack')}",
                wait_until="domcontentloaded",
            )
            page.wait_for_function(
                "(() => {"
                "  const input = document.querySelector('.pack-line .pack-line-quantity');"
                "  return !!input"
                "    && input.classList.contains('is-ui-number-input-enhanced')"
                "    && !!input.closest('.ui-number-input')"
                "    && !!input.closest('.ui-number-input').querySelector('.ui-number-input-controls');"
                "})()"
            )

            page.locator("#pack-add-line").click()
            page.wait_for_function("() => document.querySelectorAll('.pack-line').length === 2")
            page.wait_for_function(
                "(() => {"
                "  const inputs = Array.from(document.querySelectorAll('.pack-line .pack-line-quantity'));"
                "  return inputs.length === 2"
                "    && inputs.every(input => input.classList.contains('is-ui-number-input-enhanced'))"
                "    && inputs.every(input => !!input.closest('.ui-number-input'))"
                "    && inputs.every(input => !!input.closest('.ui-number-input')"
                "      .querySelector('.ui-number-input-controls'));"
                "})()"
            )

            self.assertEqual(
                page.locator('.pack-line [data-ui-number-input-action="increment"]').count(),
                2,
            )
            self.assertEqual(
                page.locator('.pack-line [data-ui-number-input-action="decrement"]').count(),
                2,
            )
            context.close()
            browser.close()

    def test_scan_pack_barcode_detector_resolves_product_select_and_restarts_cleanly(self):
        Product.objects.create(
            sku="UI-002",
            barcode="UI-BAR-002",
            name="UI Barcode Product",
            weight_g=120,
            volume_cm3=180,
            default_location=self.location,
            qr_code_image="qr_codes/test-barcode.png",
        )
        init_script = """
window.__scanCodes = ['UI-BAR-002', 'UI-BAR-002'];
window.__getUserMediaCalls = 0;
window.__videoLoadCalls = 0;
Object.defineProperty(navigator, 'mediaDevices', {
  value: {
    getUserMedia: async () => {
      window.__getUserMediaCalls += 1;
      return new MediaStream();
    },
  },
  configurable: true,
});
window.BarcodeDetector = class {
  async detect() {
    const code = window.__scanCodes.shift();
    return code ? [{ rawValue: code }] : [];
  }
};
HTMLMediaElement.prototype.play = function() {
  return Promise.resolve();
};
HTMLMediaElement.prototype.pause = function() {};
HTMLMediaElement.prototype.load = function() {
  window.__videoLoadCalls += 1;
};
"""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context(
                browser,
                init_script=init_script,
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}{reverse('scan:scan_pack')}",
                wait_until="domcontentloaded",
            )
            scan_button = page.locator('[data-scan-target="id_pack_line_1_product_code"]')
            page.wait_for_selector('[data-scan-target="id_pack_line_1_product_code"]')

            scan_button.tap()
            page.wait_for_function(
                "() => document.getElementById('id_pack_line_1_product_code').value === 'UI-002'"
            )
            page.wait_for_function(
                "() => !document.getElementById('scan-overlay').classList.contains('active')"
            )
            page.wait_for_function(
                "() => window.__getUserMediaCalls === 1 && window.__videoLoadCalls >= 1"
            )
            self.assertNotEqual(
                page.evaluate(
                    "() => document.activeElement"
                    " ? document.activeElement.getAttribute('data-scan-target') || ''"
                    " : ''"
                ),
                "id_pack_line_1_product_code",
            )

            scan_button.tap()
            page.wait_for_function("() => window.__getUserMediaCalls === 2")
            page.wait_for_function(
                "() => !document.getElementById('scan-overlay').classList.contains('active')"
            )
            self.assertEqual(
                page.locator("#id_pack_line_1_product_code").input_value(),
                "UI-002",
            )
            context.close()
            browser.close()
