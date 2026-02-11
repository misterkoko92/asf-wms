from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_is_simplified_and_has_connection_block(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plateforme logistique")
        self.assertContains(
            response,
            "Gestion des stocks, reception de produits et preparation des expedition",
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
        self.assertContains(response, "Mot de passe oublie")
        self.assertContains(response, reverse("portal:portal_account_request"))
        self.assertContains(response, reverse("home"))
