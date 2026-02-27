from django.test import TestCase, override_settings
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_is_simplified_and_has_connection_block(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plateforme logistique")
        self.assertContains(
            response,
            "Gestion des stocks, réception de produits et préparation des expéditions",
        )
        self.assertContains(response, "Connexion")
        self.assertContains(response, 'action="/admin/login/?next=/scan/"')
        self.assertContains(response, reverse("password_help"))
        self.assertContains(response, reverse("portal:portal_account_request"))

        self.assertNotContains(response, "Acces rapide")
        self.assertNotContains(response, "Flux recommande")
        self.assertNotContains(response, "Ouvrir Scan PWA")
        self.assertNotContains(response, "Aller a l administration")

    def test_password_help_page_exists(self):
        response = self.client.get(reverse("password_help"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mot de passe oubli")
        self.assertContains(response, reverse("portal:portal_account_request"))
        self.assertContains(response, reverse("home"))

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_home_page_includes_bootstrap_assets_when_enabled(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "family=DM+Sans")
        self.assertContains(response, "family=Nunito+Sans")
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        )
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        )
        self.assertContains(response, "home-bootstrap-enabled")
        self.assertContains(response, "form-control")
        self.assertContains(response, "btn btn-primary")

    @override_settings(SCAN_BOOTSTRAP_ENABLED=True)
    def test_password_help_page_includes_bootstrap_assets_when_enabled(self):
        response = self.client.get(reverse("password_help"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "family=DM+Sans")
        self.assertContains(response, "family=Nunito+Sans")
        self.assertContains(
            response,
            "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        )
        self.assertContains(response, "home-bootstrap-enabled")
