from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.billing_permissions import BILLING_STAFF_GROUP_NAME
from wms.models import (
    AssociationProfile,
    BillingAssociationPriceOverride,
    BillingBaseUnitSource,
    BillingComputationProfile,
    BillingExtraUnitMode,
    BillingServiceCatalogItem,
)


class ScanBillingViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-billing-staff",
            is_staff=True,
        )
        self.billing_user = get_user_model().objects.create_user(
            username="scan-billing-operator",
            is_staff=True,
        )
        billing_group, _ = Group.objects.get_or_create(name=BILLING_STAFF_GROUP_NAME)
        self.billing_user.groups.add(billing_group)
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-billing-admin",
            email="scan-billing-admin@example.com",
        )

    def _create_association_profile(
        self, *, username: str = "scan-billing-association"
    ) -> AssociationProfile:
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )
        contact = Contact.objects.create(
            name=f"Association {username}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return AssociationProfile.objects.create(user=user, contact=contact)

    def test_scan_billing_settings_requires_superuser(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("scan:scan_billing_settings"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.billing_user)
        response = self.client.get(reverse("scan:scan_billing_settings"))
        self.assertEqual(response.status_code, 403)

    def test_scan_billing_equivalence_requires_superuser(self):
        self.client.force_login(self.billing_user)
        response = self.client.get(reverse("scan:scan_billing_equivalence"))
        self.assertEqual(response.status_code, 403)

    def test_scan_billing_editor_requires_billing_staff_or_superuser(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("scan:scan_billing_editor"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.billing_user)
        response = self.client.get(reverse("scan:scan_billing_editor"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "billing_editor")

    def test_scan_billing_routes_render_for_superuser(self):
        self.client.force_login(self.superuser)
        expectations = {
            "scan:scan_billing_settings": "billing_settings",
            "scan:scan_billing_equivalence": "billing_equivalence",
            "scan:scan_billing_editor": "billing_editor",
        }

        for route_name, active in expectations.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["active"], active)

    def test_scan_billing_routes_redirect_anonymous_to_admin_login(self):
        response = self.client.get(reverse("scan:scan_billing_editor"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_scan_billing_settings_creates_computation_profile(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_billing_settings"),
            {
                "action": "save_profile",
                "label": "Receipt linked standard",
                "applies_when_receipts_linked": "True",
                "base_unit_source": BillingBaseUnitSource.ALLOCATED_RECEIVED_UNITS,
                "base_step_size": 10,
                "base_step_price": "75.00",
                "extra_unit_mode": BillingExtraUnitMode.SHIPPED_MINUS_ALLOCATED_RECEIVED,
                "extra_unit_price": "10.00",
                "allow_manual_override": "on",
                "is_default_for_receipt_linked": "on",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        profile = BillingComputationProfile.objects.get(label="Receipt linked standard")
        self.assertEqual(profile.base_step_size, 10)
        self.assertEqual(profile.base_step_price, Decimal("75.00"))

    def test_scan_billing_settings_updates_computation_profile(self):
        profile = BillingComputationProfile.objects.create(
            code="shipment-standard",
            label="Shipment standard",
            base_step_size=10,
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_billing_settings"),
            {
                "action": "save_profile",
                "profile_id": profile.id,
                "label": "Shipment standard updated",
                "applies_when_receipts_linked": "",
                "base_unit_source": BillingBaseUnitSource.SHIPPED_UNITS,
                "base_step_size": 20,
                "base_step_price": "150.00",
                "extra_unit_mode": BillingExtraUnitMode.NONE,
                "extra_unit_price": "0.00",
                "allow_manual_override": "",
                "is_default_for_shipment_only": "on",
                "is_default_for_receipt_linked": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.label, "Shipment standard updated")
        self.assertEqual(profile.base_step_size, 20)

    def test_scan_billing_settings_updates_service_catalog_item(self):
        service = BillingServiceCatalogItem.objects.create(
            label="Export declaration",
            default_unit_price=Decimal("45.00"),
            service_type="export",
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_billing_settings"),
            {
                "action": "save_service",
                "service_id": service.id,
                "label": "Export declaration premium",
                "description": "Handled by ASF",
                "service_type": "export",
                "default_unit_price": "55.00",
                "default_currency": "EUR",
                "display_order": 3,
                "is_discount": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        service.refresh_from_db()
        self.assertEqual(service.label, "Export declaration premium")
        self.assertEqual(service.default_unit_price, Decimal("55.00"))

    def test_scan_billing_settings_creates_association_price_override(self):
        association_profile = self._create_association_profile()
        computation_profile = BillingComputationProfile.objects.create(
            code="shipment-standard",
            label="Shipment standard",
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_billing_settings"),
            {
                "action": "save_override",
                "association_profile": association_profile.id,
                "service_catalog_item": "",
                "computation_profile": computation_profile.id,
                "overridden_amount": "62.00",
                "currency": "EUR",
                "notes": "Special annual agreement",
            },
        )

        self.assertEqual(response.status_code, 302)
        override = BillingAssociationPriceOverride.objects.get(
            association_billing_profile=association_profile.billing_profile
        )
        self.assertEqual(override.computation_profile_id, computation_profile.id)
        self.assertEqual(override.overridden_amount, Decimal("62.00"))

    def test_scan_billing_settings_updates_association_price_override(self):
        association_profile = self._create_association_profile(username="scan-billing-override")
        service = BillingServiceCatalogItem.objects.create(
            label="Pickup",
            default_unit_price=Decimal("30.00"),
        )
        override = BillingAssociationPriceOverride.objects.create(
            association_billing_profile=association_profile.billing_profile,
            service_catalog_item=service,
            overridden_amount=Decimal("25.00"),
            currency="EUR",
        )
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_billing_settings"),
            {
                "action": "save_override",
                "override_id": override.id,
                "association_profile": association_profile.id,
                "service_catalog_item": service.id,
                "computation_profile": "",
                "overridden_amount": "27.50",
                "currency": "CHF",
                "notes": "Updated agreement",
            },
        )

        self.assertEqual(response.status_code, 302)
        override.refresh_from_db()
        self.assertEqual(override.overridden_amount, Decimal("27.50"))
        self.assertEqual(override.currency, "CHF")

    def test_scan_billing_settings_page_renders_configured_records(self):
        association_profile = self._create_association_profile(username="scan-billing-list")
        computation_profile = BillingComputationProfile.objects.create(
            code="shipment-standard",
            label="Shipment standard",
            base_step_price=Decimal("75.00"),
        )
        service = BillingServiceCatalogItem.objects.create(
            label="Pickup",
            default_unit_price=Decimal("30.00"),
        )
        BillingAssociationPriceOverride.objects.create(
            association_billing_profile=association_profile.billing_profile,
            service_catalog_item=service,
            overridden_amount=Decimal("25.00"),
            currency="EUR",
        )
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_billing_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shipment standard")
        self.assertContains(response, "Pickup")
        self.assertContains(response, association_profile.contact.name)
        self.assertContains(response, "save_profile")
        self.assertContains(response, "save_service")
        self.assertContains(response, "save_override")
