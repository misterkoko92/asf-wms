from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from wms.billing_permissions import BILLING_STAFF_GROUP_NAME


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
