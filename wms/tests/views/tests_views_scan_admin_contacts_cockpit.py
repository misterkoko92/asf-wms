from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ScanAdminContactsCockpitViewTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-cockpit-superuser",
            password="pass1234",
            email="scan-cockpit-superuser@example.com",
        )

    def test_scan_admin_contacts_renders_org_role_cockpit(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pilotage contacts org-role")
        self.assertContains(response, "Recherche et filtres")
        self.assertContains(response, "Actions metier")
        self.assertEqual(response.context["active"], "admin_contacts")
