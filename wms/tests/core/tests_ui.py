import os
import unittest
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import Location, Product, Warehouse
from wms.models import AssociationProfile

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
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        warehouse = Warehouse.objects.create(name="UI WH", code="UI")
        location = Location.objects.create(
            warehouse=warehouse, zone="A", aisle="01", shelf="001"
        )
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


@unittest.skipUnless(os.getenv("RUN_UI_TESTS") == "1", "UI tests disabled")
@unittest.skipIf(sync_playwright is None, "Playwright not installed")
@unittest.skipUnless(
    (settings.BASE_DIR / "frontend-next" / "out").exists(),
    "frontend-next/out missing (run npm run build first)",
)
class NextUiTests(StaticLiveServerTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="next-ui-staff",
            password="pass1234",
            is_staff=True,
        )
        self.portal_user = user_model.objects.create_user(
            username="next-ui-portal",
            password="pass1234",
        )
        association_contact = Contact.objects.create(
            name="Association Next UI",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=association_contact,
        )

        self.staff_session_cookie = self._session_cookie_for_user(self.staff_user)
        self.portal_session_cookie = self._session_cookie_for_user(self.portal_user)

    def _session_cookie_for_user(self, user):
        auth_client = Client()
        auth_client.force_login(user)
        return auth_client.cookies[settings.SESSION_COOKIE_NAME].value

    def _new_context_with_session(self, browser, *, session_cookie):
        context = browser.new_context()
        context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session_cookie,
                    "url": self.live_server_url,
                }
            ]
        )
        return context

    def test_next_scan_dashboard_loads_for_staff(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, session_cookie=self.staff_session_cookie
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            heading = page.locator("h1").inner_text()
            self.assertIn("Dashboard mission control", heading)
            self.assertTrue(page.get_by_text("Retour interface actuelle").count())
            context.close()
            browser.close()

    def test_next_shipment_documents_invalid_id_shows_inline_error(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, session_cookie=self.staff_session_cookie
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipment-documents/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Shipment ID").fill("abc")
            page.get_by_role("button", name="Charger").click()
            page.wait_for_selector(".api-error")
            error_text = page.locator(".api-error").inner_text()
            self.assertIn("Identifiant expedition invalide.", error_text)
            context.close()
            browser.close()

    def test_next_portal_dashboard_loads_for_association_user(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, session_cookie=self.portal_session_cookie
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/portal/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            heading = page.locator("h1").inner_text()
            self.assertIn("Portal dashboard", heading)
            self.assertTrue(page.get_by_text("Retour interface actuelle").count())
            context.close()
            browser.close()
