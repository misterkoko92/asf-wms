import os
import unittest
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact, ContactTag, ContactType
from contacts.tagging import TAG_CORRESPONDENT, TAG_RECIPIENT, TAG_SHIPPER
from wms.models import (
    AssociationContactTitle,
    AssociationProfile,
    AssociationRecipient,
    Carton,
    CartonItem,
    CartonStatus,
    Destination,
    Document,
    DocumentType,
    Order,
    Location,
    ProductLotStatus,
    PrintTemplate,
    Product,
    ProductLot,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    TEMP_SHIPMENT_REFERENCE_PREFIX,
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
        self.superuser_user = user_model.objects.create_user(
            username="next-ui-superuser",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
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

        self.shipper_contact = Contact.objects.create(
            name="Next UI Shipper",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_contact = Contact.objects.create(
            name="Next UI Recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent_contact = Contact.objects.create(
            name="Next UI Correspondent",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="RUN",
            iata_code="RUN-NEXT-UI",
            country="France",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.secondary_destination = Destination.objects.create(
            city="TNR",
            iata_code="TNR-NEXT-UI",
            country="Madagascar",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        shipper_tag, _ = ContactTag.objects.get_or_create(name=TAG_SHIPPER[0])
        recipient_tag, _ = ContactTag.objects.get_or_create(name=TAG_RECIPIENT[0])
        correspondent_tag, _ = ContactTag.objects.get_or_create(name=TAG_CORRESPONDENT[0])
        self.shipper_contact.tags.add(shipper_tag)
        self.recipient_contact.tags.add(recipient_tag)
        self.correspondent_contact.tags.add(correspondent_tag)
        self.shipper_contact.destinations.add(self.destination)
        self.recipient_contact.destinations.add(self.destination)
        self.correspondent_contact.destinations.add(self.destination)
        self.shipper_contact.destinations.add(self.secondary_destination)
        self.recipient_contact.destinations.add(self.secondary_destination)
        self.correspondent_contact.destinations.add(self.secondary_destination)
        self.docs_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="1 Rue Next UI",
            destination_country="France",
            created_by=self.staff_user,
        )
        self.secondary_destination_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.secondary_destination,
            destination_address="1 Rue Secondary",
            destination_country="Madagascar",
            created_by=self.staff_user,
        )
        self.available_carton = Carton.objects.create(
            code="NEXT-UI-CARTON-AVAILABLE",
            status=CartonStatus.PACKED,
        )
        self.workflow_tracking_shipment = Shipment.objects.create(
            status=ShipmentStatus.SHIPPED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="1 Rue Next UI",
            destination_country="France",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=self.workflow_tracking_shipment,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Ops",
            actor_structure="ASF",
            comments="planned",
            created_by=self.staff_user,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=self.workflow_tracking_shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Ops",
            actor_structure="ASF",
            comments="boarding",
            created_by=self.staff_user,
        )
        stock_warehouse = Warehouse.objects.create(name="Next UI Stock WH", code="NUI")
        stock_location = Location.objects.create(
            warehouse=stock_warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.stock_product = Product.objects.create(
            sku="NEXT-UI-STOCK-001",
            name="Next UI Stock Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        self.stock_secondary_product = Product.objects.create(
            sku="NEXT-UI-STOCK-002",
            name="Next UI Secondary Stock Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        self.dashboard_low_stock_product = Product.objects.create(
            sku="NEXT-UI-DASH-LOW-001",
            name="Next UI Dashboard Low Stock Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.dashboard_low_stock_product,
            lot_code="NEXT-UI-DASH-LOW-LOT",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            quantity_reserved=0,
            location=stock_location,
        )
        self.stock_filter_primary_product = Product.objects.create(
            sku="NEXT-UI-STOCK-FILTER-001",
            name="Next UI Filter Primary Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.stock_filter_primary_product,
            lot_code="NEXT-UI-STOCK-FILTER-LOT-1",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=8,
            quantity_reserved=0,
            location=stock_location,
        )
        ProductLot.objects.create(
            product=self.stock_secondary_product,
            lot_code="NEXT-UI-STOCK-LOT-2",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=5,
            quantity_reserved=0,
            location=stock_location,
        )
        self.shipment_pack_product = Product.objects.create(
            sku="NEXT-UI-PACK-001",
            name="Next UI Pack Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        self.shipment_pack_lot = ProductLot.objects.create(
            product=self.shipment_pack_product,
            lot_code="NEXT-UI-PACK-LOT",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=10,
            quantity_reserved=0,
            location=stock_location,
        )
        self.cartons_ready_carton = Carton.objects.create(
            code="NEXT-UI-CARTON-READY",
            status=CartonStatus.PACKED,
        )
        CartonItem.objects.create(
            carton=self.cartons_ready_carton,
            product_lot=self.shipment_pack_lot,
            quantity=2,
        )
        self.portal_product = Product.objects.create(
            sku="NEXT-UI-PORTAL-001",
            name="Next UI Portal Product",
            brand="ASF",
            default_location=stock_location,
            is_active=True,
            qr_code_image="qr_codes/test.png",
        )
        ProductLot.objects.create(
            product=self.portal_product,
            lot_code="NEXT-UI-PORTAL-LOT",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=25,
            quantity_reserved=0,
            location=stock_location,
        )
        self.portal_recipient = AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=self.destination,
            name="Next UI Portal Recipient",
            structure_name="Next UI Portal Recipient",
            contact_title=AssociationContactTitle.MR,
            contact_last_name="Portal",
            contact_first_name="User",
            phones="0102030405",
            emails="portal.recipient@example.org",
            address_line1="10 Rue Portal",
            postal_code="75001",
            city="Paris",
            country="France",
            notify_deliveries=True,
            is_delivery_contact=True,
        )

        self.staff_auth_cookies = self._auth_cookies_for_user(self.staff_user)
        self.superuser_auth_cookies = self._auth_cookies_for_user(self.superuser_user)
        self.portal_auth_cookies = self._auth_cookies_for_user(self.portal_user)

    def _auth_cookies_for_user(self, user):
        auth_client = Client()
        auth_client.get(reverse("admin:login"))
        auth_client.force_login(user)
        return {
            "session": auth_client.cookies[settings.SESSION_COOKIE_NAME].value,
            "csrf": auth_client.cookies[settings.CSRF_COOKIE_NAME].value,
        }

    def _new_context_with_session(self, browser, *, auth_cookies):
        context = browser.new_context()
        cookies = [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": auth_cookies["session"],
                "url": self.live_server_url,
            },
            {
                "name": settings.CSRF_COOKIE_NAME,
                "value": auth_cookies["csrf"],
                "url": self.live_server_url,
            },
        ]
        context.add_cookies(cookies)
        return context

    def test_next_scan_dashboard_loads_for_staff(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
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

    def test_next_scan_dashboard_displays_live_timeline_and_actions(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(ref) => document.body.innerText.includes(ref)",
                arg=self.workflow_tracking_shipment.reference,
            )
            page.wait_for_function(
                "(sku) => document.body.innerText.includes(sku)",
                arg=self.stock_secondary_product.sku,
            )
            context.close()
            browser.close()

    def test_next_scan_dashboard_filters_by_destination(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                """
                (value) => {
                  const cards = Array.from(document.querySelectorAll(".kpi-card"));
                  const card = cards.find((item) =>
                    (item.textContent || "").includes("Expeditions ouvertes")
                  );
                  return !!card && (card.textContent || "").includes(String(value));
                }
                """,
                arg=3,
            )
            page.get_by_label("Destination").select_option(
                str(self.secondary_destination.id)
            )
            page.get_by_role("button", name="Filtrer").click()
            page.wait_for_function(
                """
                (value) => {
                  const cards = Array.from(document.querySelectorAll(".kpi-card"));
                  const card = cards.find((item) =>
                    (item.textContent || "").includes("Expeditions ouvertes")
                  );
                  return !!card && (card.textContent || "").includes(String(value));
                }
                """,
                arg=1,
            )
            context.close()
            browser.close()

    def test_next_scan_dashboard_displays_low_stock_table(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(title) => document.body.innerText.toLowerCase().includes(title)",
                arg="stock sous seuil",
            )
            page.wait_for_function(
                """
                (sku) => {
                  const panels = Array.from(document.querySelectorAll("article.panel"));
                  const panel = panels.find((item) =>
                    (item.textContent || "").toLowerCase().includes("stock sous seuil")
                  );
                  return !!panel && (panel.textContent || "").includes(sku);
                }
                """,
                arg=self.dashboard_low_stock_product.sku,
            )
            context.close()
            browser.close()

    def test_next_scan_dashboard_filters_by_period(self):
        old_shipment = Shipment.objects.create(
            status=ShipmentStatus.PLANNED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="12 Rue Legacy",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=old_shipment.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                """
                (value) => {
                  const cards = Array.from(document.querySelectorAll(".kpi-card"));
                  const card = cards.find((item) =>
                    (item.textContent || "").includes("Expeditions creees")
                  );
                  return !!card && (card.textContent || "").includes(String(value));
                }
                """,
                arg=3,
            )
            page.get_by_label("Periode KPI").select_option("30d")
            page.get_by_role("button", name="Filtrer").click()
            page.wait_for_function(
                """
                (value) => {
                  const cards = Array.from(document.querySelectorAll(".kpi-card"));
                  const card = cards.find((item) =>
                    (item.textContent || "").includes("Expeditions creees")
                  );
                  return !!card && (card.textContent || "").includes(String(value));
                }
                """,
                arg=4,
            )
            context.close()
            browser.close()

    def test_next_shipment_documents_invalid_id_shows_inline_error(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
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
                browser, auth_cookies=self.portal_auth_cookies
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

    def test_next_shipment_documents_upload_and_delete_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipment-documents/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Shipment ID").fill(str(self.docs_shipment.id))
            page.get_by_role("button", name="Charger").click()
            page.wait_for_selector(".api-ok")
            page.locator('input[type="file"]').set_input_files(
                {
                    "name": "manifest-next-ui.pdf",
                    "mimeType": "application/pdf",
                    "buffer": b"%PDF-1.4 Next UI test",
                }
            )
            page.get_by_role("button", name="Upload").click()
            page.wait_for_function(
                "document.body.innerText.includes('Document televerse.')"
            )
            self.assertGreater(page.get_by_role("button", name="Supprimer").count(), 0)
            page.get_by_role("button", name="Supprimer").first.click()
            page.wait_for_function(
                "document.body.innerText.includes('Document supprime.')"
            )
            context.close()
            browser.close()
        self.assertEqual(
            Document.objects.filter(
                shipment=self.docs_shipment,
                doc_type=DocumentType.ADDITIONAL,
            ).count(),
            0,
        )

    def test_next_templates_save_and_reset_workflow(self):
        doc_type = ""
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.superuser_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/templates/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_selector("select")
            doc_type = page.locator("select").input_value()
            self.assertTrue(doc_type)
            page.locator("textarea").fill(
                '{\n  "blocks": [{"id": "next-ui-test", "type": "text", "text": "Next UI"}]\n}'
            )
            page.get_by_role("button", name="Sauver").click()
            page.wait_for_function(
                "document.body.innerText.includes('Template enregistre.')"
            )
            page.get_by_role("button", name="Reset").click()
            page.wait_for_function(
                "document.body.innerText.includes('Template reinitialise.')"
            )
            context.close()
            browser.close()
        template = PrintTemplate.objects.get(doc_type=doc_type)
        self.assertEqual(template.layout, {})
        self.assertEqual(template.versions.count(), 2)

    def test_next_stock_update_and_out_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/stock/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Product code (MAJ)").fill(self.stock_product.sku)
            page.get_by_label("Quantite (MAJ)").fill("4")
            page.get_by_label("Expire le (MAJ)").fill("2026-12-31")
            page.get_by_label("Lot (MAJ)").fill("NEXT-LOT-UI")
            page.get_by_role("button", name="Valider MAJ").click()
            page.wait_for_function(
                "document.body.innerText.includes('Stock mis a jour.')"
            )

            page.get_by_label("Product code (Sortie)").fill(self.stock_product.sku)
            page.get_by_label("Quantite (Sortie)").fill("1")
            page.get_by_label("Raison (Sortie)").fill("next_ui_test")
            page.get_by_role("button", name="Valider sortie").click()
            page.wait_for_function(
                "document.body.innerText.includes('Sortie stock enregistree.')"
            )
            context.close()
            browser.close()
        self.assertEqual(ProductLot.objects.filter(product=self.stock_product).count(), 1)
        total_quantity = ProductLot.objects.filter(product=self.stock_product).aggregate(
            total=Sum("quantity_on_hand")
        )["total"]
        self.assertEqual(total_quantity, 3)

    def test_next_stock_filters_by_query_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/stock/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(skus) => document.body.innerText.includes(skus.primary) && "
                "document.body.innerText.includes(skus.secondary)",
                arg={
                    "primary": self.stock_filter_primary_product.sku,
                    "secondary": self.stock_secondary_product.sku,
                },
            )
            page.get_by_label("Recherche").fill(self.stock_filter_primary_product.sku)
            page.get_by_role("button", name="Filtrer").click()
            page.wait_for_function(
                "(skus) => document.body.innerText.includes(skus.primary) && "
                "!document.body.innerText.includes(skus.secondary)",
                arg={
                    "primary": self.stock_filter_primary_product.sku,
                    "secondary": self.stock_secondary_product.sku,
                },
            )
            context.close()
            browser.close()

    def test_next_shipment_create_tracking_close_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipment-create/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Destination ID").select_option(str(self.destination.id))
            page.get_by_label("Expediteur ID").select_option(str(self.shipper_contact.id))
            page.get_by_label("Destinataire ID").select_option(str(self.recipient_contact.id))
            page.get_by_label("Correspondant ID").select_option(
                str(self.correspondent_contact.id)
            )
            page.get_by_label("Carton ID").select_option(str(self.available_carton.id))
            page.get_by_role("button", name="Creer expedition").click()
            page.wait_for_function(
                "document.body.innerText.includes('Expedition creee.')"
            )

            page.get_by_label("Shipment ID (Tracking)").fill(
                str(self.workflow_tracking_shipment.id)
            )
            page.get_by_label("Status tracking").select_option(
                ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
            )
            page.get_by_role("button", name="Envoyer tracking").click()
            page.wait_for_function(
                "document.body.innerText.includes('Suivi mis a jour.')"
            )

            page.get_by_label("Status tracking").select_option(
                ShipmentTrackingStatus.RECEIVED_RECIPIENT
            )
            page.get_by_role("button", name="Envoyer tracking").click()
            page.wait_for_function(
                "document.body.innerText.includes('Suivi mis a jour.')"
            )

            page.get_by_label("Shipment ID (Cloture)").fill(
                str(self.workflow_tracking_shipment.id)
            )
            page.get_by_role("button", name="Cloturer expedition").click()
            page.wait_for_function(
                "document.body.innerText.includes('Dossier cloture.')"
            )
            context.close()
            browser.close()
        self.available_carton.refresh_from_db()
        self.assertEqual(self.available_carton.status, CartonStatus.ASSIGNED)
        self.assertIsNotNone(self.available_carton.shipment_id)
        self.workflow_tracking_shipment.refresh_from_db()
        self.assertIsNotNone(self.workflow_tracking_shipment.closed_at)

    def test_next_shipment_create_from_product_line_workflow(self):
        carton_ids_before = set(Carton.objects.values_list("id", flat=True))
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipment-create/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Destination ID").select_option(str(self.destination.id))
            page.get_by_label("Expediteur ID").select_option(str(self.shipper_contact.id))
            page.get_by_label("Destinataire ID").select_option(str(self.recipient_contact.id))
            page.get_by_label("Correspondant ID").select_option(
                str(self.correspondent_contact.id)
            )
            page.get_by_label("Carton ID").select_option("")
            page.get_by_label("Product code (Creation)").fill(
                self.shipment_pack_product.sku
            )
            page.get_by_label("Quantite (Creation)").fill("2")
            page.get_by_role("button", name="Creer expedition").click()
            page.wait_for_function(
                "document.body.innerText.includes('Expedition creee.')"
            )
            context.close()
            browser.close()

        new_cartons = Carton.objects.exclude(id__in=carton_ids_before)
        self.assertEqual(new_cartons.count(), 1)
        created_carton = new_cartons.first()
        self.assertIsNotNone(created_carton)
        self.assertEqual(created_carton.status, CartonStatus.ASSIGNED)
        self.assertIsNotNone(created_carton.shipment_id)
        self.assertTrue(
            created_carton.cartonitem_set.filter(
                product_lot__product=self.shipment_pack_product,
                quantity=2,
            ).exists()
        )
        self.shipment_pack_lot.refresh_from_db()
        self.assertEqual(self.shipment_pack_lot.quantity_on_hand, 8)

    def test_next_shipments_tracking_route_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-tracking/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.get_by_label("Shipment ID (Tracking)").fill(
                str(self.workflow_tracking_shipment.id)
            )
            page.get_by_label("Status tracking").select_option(
                ShipmentTrackingStatus.RECEIVED_CORRESPONDENT
            )
            page.get_by_role("button", name="Envoyer tracking").click()
            page.wait_for_function(
                "document.body.innerText.includes('Suivi mis a jour.')"
            )

            page.get_by_label("Status tracking").select_option(
                ShipmentTrackingStatus.RECEIVED_RECIPIENT
            )
            page.get_by_role("button", name="Envoyer tracking").click()
            page.wait_for_function(
                "document.body.innerText.includes('Suivi mis a jour.')"
            )

            page.get_by_label("Shipment ID (Cloture)").fill(
                str(self.workflow_tracking_shipment.id)
            )
            page.get_by_role("button", name="Cloturer expedition").click()
            page.wait_for_function(
                "document.body.innerText.includes('Dossier cloture.')"
            )
            context.close()
            browser.close()
        self.workflow_tracking_shipment.refresh_from_db()
        self.assertIsNotNone(self.workflow_tracking_shipment.closed_at)

    def test_next_shipments_tracking_route_lists_shipments(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-tracking/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(shipmentRef) => document.body.innerText.includes(shipmentRef)",
                arg=self.workflow_tracking_shipment.reference,
            )
            context.close()
            browser.close()

    def test_next_shipments_tracking_route_close_buttons_match_state_styles(self):
        closable_shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="6 Rue Next UI",
            destination_country="France",
            created_by=self.staff_user,
        )
        for status in (
            ShipmentTrackingStatus.PLANNED,
            ShipmentTrackingStatus.BOARDING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ):
            ShipmentTrackingEvent.objects.create(
                shipment=closable_shipment,
                status=status,
                actor_name="Ops",
                actor_structure="ASF",
                comments="step",
                created_by=self.staff_user,
            )

        closed_shipment = Shipment.objects.create(
            status=ShipmentStatus.DELIVERED,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="7 Rue Next UI",
            destination_country="France",
            created_by=self.staff_user,
            closed_at=timezone.now(),
            closed_by=self.staff_user,
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-tracking/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(shipmentRef) => document.body.innerText.includes(shipmentRef)",
                arg=closable_shipment.reference,
            )

            closable_button = page.locator(
                "tr",
                has_text=closable_shipment.reference,
            ).get_by_role("button", name="Clore le dossier")
            self.assertIn("btn-success-soft", closable_button.get_attribute("class") or "")

            blocked_button = page.locator(
                "tr",
                has_text=self.workflow_tracking_shipment.reference,
            ).get_by_role("button", name="Clore le dossier")
            self.assertIn("btn-danger-soft", blocked_button.get_attribute("class") or "")

            page.get_by_label("Dossiers clos").select_option("all")
            page.get_by_role("button", name="Filtrer").click()
            page.wait_for_function(
                "(shipmentRef) => document.body.innerText.includes(shipmentRef)",
                arg=closed_shipment.reference,
            )
            closed_button = page.locator(
                "tr",
                has_text=closed_shipment.reference,
            ).get_by_role("button", name="Dossier cloture")
            self.assertIn("btn-success-soft", closed_button.get_attribute("class") or "")
            self.assertTrue(closed_button.is_disabled())
            context.close()
            browser.close()

    def test_next_shipments_ready_route_lists_shipments(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-ready/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(shipmentRef) => document.body.innerText.includes(shipmentRef)",
                arg=self.docs_shipment.reference,
            )
            context.close()
            browser.close()

    def test_next_shipments_ready_route_shows_legacy_document_links(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-ready/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(text) => document.body.innerText.includes(text)",
                arg="Documents",
            )
            page.wait_for_function(
                "() => document.querySelectorAll(\"a[href*='packing_list_shipment']\").length > 0"
            )
            page.wait_for_function(
                "() => document.querySelectorAll(\"a[href*='donation_certificate']\").length > 0"
            )
            context.close()
            browser.close()

    def test_next_shipments_ready_route_archives_stale_drafts(self):
        stale_draft = Shipment.objects.create(
            status=ShipmentStatus.DRAFT,
            reference=f"{TEMP_SHIPMENT_REFERENCE_PREFIX}77",
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name=self.correspondent_contact.name,
            correspondent_contact_ref=self.correspondent_contact,
            destination=self.destination,
            destination_address="5 Rue Next UI",
            destination_country="France",
            created_by=self.staff_user,
        )
        Shipment.objects.filter(pk=stale_draft.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/shipments-ready/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(text) => document.body.innerText.includes(text)",
                arg="Archiver brouillons anciens",
            )
            page.get_by_role("button", name="Archiver brouillons anciens").click()
            page.wait_for_function(
                "(text) => document.body.innerText.includes(text)",
                arg="brouillon(s) temporaire(s) archives.",
            )
            context.close()
            browser.close()

        stale_draft.refresh_from_db()
        self.assertIsNotNone(stale_draft.archived_at)

    def test_next_cartons_route_lists_cartons(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.staff_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/scan/cartons/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")
            page.wait_for_function(
                "(cartonCode) => document.body.innerText.includes(cartonCode)",
                arg=self.cartons_ready_carton.code,
            )
            context.close()
            browser.close()

    def test_next_portal_order_recipient_account_workflow(self):
        created_recipient_name = "Next UI Recipient Created"
        updated_recipient_name = "Next UI Recipient Updated"
        updated_association_name = "Association Next UI Updated"
        updated_contact_email = "portal.updated@example.org"
        before_order_count = Order.objects.filter(
            association_contact=self.portal_recipient.association_contact
        ).count()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = self._new_context_with_session(
                browser, auth_cookies=self.portal_auth_cookies
            )
            page = context.new_page()
            page.goto(
                f"{self.live_server_url}/app/portal/dashboard/",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("h1")

            page.get_by_label("Destination ID (Commande)").select_option(
                str(self.destination.id)
            )
            page.get_by_label("Destinataire ID (Commande)").select_option(
                str(self.portal_recipient.id)
            )
            page.get_by_label("Product ID (Commande)").fill(str(self.portal_product.id))
            page.get_by_label("Quantite (Commande)").fill("2")
            page.get_by_role("button", name="Envoyer commande").click()
            page.wait_for_function(
                "document.body.innerText.includes('Commande envoyee.')"
            )

            page.get_by_label("Destination ID (Destinataire)").select_option(
                str(self.destination.id)
            )
            page.get_by_label("Structure (Destinataire)").fill(created_recipient_name)
            page.get_by_label("Adresse 1 (Destinataire)").fill("20 Rue Next Portal")
            page.get_by_role("button", name="Ajouter destinataire").click()
            page.wait_for_function(
                "document.body.innerText.includes('Destinataire ajoute.')"
            )

            page.get_by_label("Structure (Edition)").fill(updated_recipient_name)
            page.get_by_role("button", name="Modifier destinataire").click()
            page.wait_for_function(
                "document.body.innerText.includes('Destinataire modifie.')"
            )

            page.get_by_label("Association name (Compte)").fill(updated_association_name)
            page.get_by_label("Adresse 1 (Compte)").fill("99 Rue Association")
            page.get_by_label("Email contact (Compte)").fill(updated_contact_email)
            page.get_by_role("button", name="Sauver compte").click()
            page.wait_for_function(
                "document.body.innerText.includes('Compte mis a jour.')"
            )

            context.close()
            browser.close()

        self.assertEqual(
            Order.objects.filter(
                association_contact=self.portal_recipient.association_contact
            ).count(),
            before_order_count + 1,
        )
        recipient = AssociationRecipient.objects.filter(
            association_contact=self.portal_recipient.association_contact,
            structure_name=updated_recipient_name,
        ).first()
        self.assertIsNotNone(recipient)
        profile = AssociationProfile.objects.get(user=self.portal_user)
        self.assertEqual(profile.contact.name, updated_association_name)
        self.assertEqual(profile.notification_emails, updated_contact_email)
