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
    Location,
    Order,
    PlanningParameterSet,
    Product,
    ShipmentRecipientOrganization,
    ShipmentValidationStatus,
    Warehouse,
)
from wms.portal_recipient_sync import sync_association_recipient_to_contact

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional test dependency
    sync_playwright = None


@unittest.skipUnless(os.getenv("RUN_UI_TESTS") == "1", "UI tests disabled")
@unittest.skipIf(sync_playwright is None, "Playwright not installed")
class ResponsiveOverflowUiTests(StaticLiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = get_user_model().objects.create_user(
            username="responsive-staff-user-with-long-name",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            email="responsive-staff-user-with-a-very-long-email@example.org",
        )
        warehouse = Warehouse.objects.create(name="Responsive Warehouse", code="RSP")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="RESPONSIVE-LONG-ZONE",
            aisle="AISLE-RESPONSIVE-001",
            shelf="SHELF-RESPONSIVE-001",
        )
        Product.objects.create(
            sku="RESPONSIVE-SUPER-LONG-PRODUCT-REFERENCE-001",
            name=(
                "Produit responsive avec nom tres long et reference continue "
                "RESPONSIVEPRODUCTNAMETHATSHOULDWRAPWITHOUTPAGEOVERFLOW"
            ),
            brand="ASF-RESPONSIVE-BRAND-WITH-LONG-LABEL",
            default_location=location,
            qr_code_image="qr_codes/responsive.png",
        )

        self.portal_user = get_user_model().objects.create_user(
            username="responsive-portal-user",
            password="pass1234",  # pragma: allowlist secret
            email="responsive-portal-user-with-a-very-long-email@example.org",
        )
        association_contact = Contact.objects.create(
            name="Association Responsive With A Long Display Name",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association-responsive-with-a-very-long-address@example.org",
        )
        ContactAddress.objects.create(
            contact=association_contact,
            address_line1="1 Rue Responsive",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=association_contact,
            must_change_password=False,
        )
        correspondent = Contact.objects.create(
            name="Correspondant Responsive",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Responsive City With Long Name",
            iata_code="RSP",
            country="Responsive Country",
            correspondent_contact=correspondent,
            is_active=True,
        )
        recipient = AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=self.destination,
            name="Destinataire Responsive With Long Visible Name",
            structure_name="Structure Responsive With Long Visible Name",
            address_line1="2 Rue Livraison Responsive",
            city="Responsive City With Long Name",
            country="Responsive Country",
            is_delivery_contact=True,
            is_active=True,
        )
        sync_association_recipient_to_contact(recipient)
        recipient_organization = ShipmentRecipientOrganization.objects.get(
            organization=recipient.synced_contact,
            destination=self.destination,
        )
        recipient_organization.validation_status = ShipmentValidationStatus.VALIDATED
        recipient_organization.save(update_fields=["validation_status"])
        Order.objects.create(
            association_contact=association_contact,
            reference="PORTAL-RESPONSIVE-SUPER-LONG-ORDER-REFERENCE-001",
            shipper_name="ASF",
            recipient_name="Destinataire Responsive With Long Visible Name",
            destination_address="2 Rue Livraison Responsive\n75001 Paris\nFrance",
            destination_country="Responsive Country",
        )

        PlanningParameterSet.objects.create(
            name="Responsive Planning Parameter Set",
            is_current=True,
        )

    def _login_session_cookie(self, user):
        client = self.client_class()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def _new_context(self, browser, *, session_value, width):
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_init_script(
            "try { delete window.Navigator.prototype.serviceWorker; } catch (error) {}"
        )
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

    def _assert_no_page_level_horizontal_overflow(self, page, *, label, width):
        overflow = page.evaluate(
            """
(() => {
  const viewportWidth = document.documentElement.clientWidth;
  const allowedLocalScroll = [
    ".table-responsive",
    ".scan-table-wrap",
    ".portal-products-table-wrap",
    ".scan-dashboard-section-nav-actions",
    ".offcanvas",
    ".offcanvas-lg",
    ".dropdown-menu"
  ];
  const visibleOverflowingElements = [];

  for (const element of Array.from(document.body.querySelectorAll("*"))) {
    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
      Number(style.opacity) === 0
    ) {
      continue;
    }
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0 || rect.right <= 0 || rect.left >= viewportWidth) {
      continue;
    }
    if (allowedLocalScroll.some((selector) => element.closest(selector))) {
      continue;
    }
    if (rect.left < -1 || rect.right > viewportWidth + 1) {
      visibleOverflowingElements.push({
        tag: element.tagName.toLowerCase(),
        id: element.id || "",
        className: String(element.className || ""),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        width: Math.round(rect.width),
        text: (element.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 90),
      });
    }
  }

  return {
    viewportWidth,
    htmlScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    visibleOverflowingElements,
  };
})()
"""
        )
        self.assertLessEqual(
            overflow["htmlScrollWidth"],
            overflow["viewportWidth"] + 1,
            f"{label} at {width}px has document overflow: {overflow}",
        )
        self.assertLessEqual(
            overflow["bodyScrollWidth"],
            overflow["viewportWidth"] + 1,
            f"{label} at {width}px has body overflow: {overflow}",
        )
        self.assertEqual(
            overflow["visibleOverflowingElements"],
            [],
            f"{label} at {width}px has visible page-level overflow: {overflow}",
        )

    def test_authenticated_shared_pages_do_not_overflow_mobile_tablet_or_desktop(self):
        staff_session = self._login_session_cookie(self.staff_user)
        portal_session = self._login_session_cookie(self.portal_user)
        pages = [
            (
                "scan-dashboard",
                staff_session,
                reverse("scan:scan_dashboard"),
                "#scan-dashboard-page-header",
            ),
            ("scan-stock", staff_session, reverse("scan:scan_stock"), ".scan-table-wrap"),
            ("scan-pack", staff_session, reverse("scan:scan_pack"), "#pack-page"),
            (
                "portal-dashboard",
                portal_session,
                reverse("portal:portal_dashboard"),
                ".portal-page-intro",
            ),
            (
                "portal-order-create",
                portal_session,
                reverse("portal:portal_order_create"),
                "#portal-order-create-form",
            ),
            (
                "planning-run-list",
                staff_session,
                reverse("planning:run_list"),
                "#planning-page-header",
            ),
        ]
        widths = [360, 390, 768, 1366]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for width in widths:
                    for label, session_value, path, ready_selector in pages:
                        with self.subTest(label=label, width=width):
                            context = self._new_context(
                                browser,
                                session_value=session_value,
                                width=width,
                            )
                            page = context.new_page()
                            page.goto(
                                f"{self.live_server_url}{path}", wait_until="domcontentloaded"
                            )
                            page.wait_for_selector(ready_selector)
                            self._assert_no_page_level_horizontal_overflow(
                                page,
                                label=label,
                                width=width,
                            )
                            context.close()
            finally:
                browser.close()
