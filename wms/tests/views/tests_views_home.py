from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def _create_staff_user(self):
        return get_user_model().objects.create_user(
            username="staff-home",
            email="staff-home@example.com",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
            is_superuser=True,
        )

    def _assert_persistent_session(self):
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertGreaterEqual(
            self.client.session.get_expiry_age(),
            settings.SESSION_COOKIE_AGE - 5,
        )

    def _assert_browser_session(self):
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_favicon_route_redirects_to_scan_icon(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/static/scan/icon.png")

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
        self.assertContains(response, 'name="remember_me_supported"')
        self.assertContains(response, 'name="remember_me"')
        self.assertContains(response, "Rester connect")
        self.assertContains(response, reverse("password_help"))
        self.assertContains(response, reverse("portal:portal_account_request"))
        self.assertContains(response, reverse("volunteer:request_account"))

        self.assertNotContains(response, "Acces rapide")
        self.assertNotContains(response, "Flux recommande")
        self.assertNotContains(response, "Ouvrir Scan PWA")
        self.assertNotContains(response, "Aller a l administration")

    def test_password_help_page_exists(self):
        response = self.client.get(reverse("password_help"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mot de passe oubli")
        self.assertContains(response, reverse("portal:portal_account_request"))
        self.assertContains(response, reverse("volunteer:request_account"))
        self.assertContains(response, reverse("home"))

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

    def test_home_pages_do_not_expose_deprecated_ui_flags(self):
        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        with self.assertRaises(KeyError):
            home_response.context["scan_bootstrap_enabled"]
        with self.assertRaises(KeyError):
            home_response.context["wms_ui_mode"]
        with self.assertRaises(KeyError):
            home_response.context["wms_ui_mode_is_next"]

        password_help_response = self.client.get(reverse("password_help"))
        self.assertEqual(password_help_response.status_code, 200)
        with self.assertRaises(KeyError):
            password_help_response.context["scan_bootstrap_enabled"]
        with self.assertRaises(KeyError):
            password_help_response.context["wms_ui_mode"]
        with self.assertRaises(KeyError):
            password_help_response.context["wms_ui_mode_is_next"]

    def test_home_login_with_remember_me_keeps_persistent_session(self):
        user = self._create_staff_user()

        response = self.client.post(
            f"{reverse('admin:login')}?next=/scan/",
            {
                "username": user.username,
                "password": "pass1234",  # pragma: allowlist secret
                "next": "/scan/",
                "remember_me_supported": "1",
                "remember_me": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/scan/")
        self._assert_persistent_session()

    def test_home_login_without_remember_me_uses_browser_session(self):
        user = self._create_staff_user()

        response = self.client.post(
            f"{reverse('admin:login')}?next=/scan/",
            {
                "username": user.username,
                "password": "pass1234",  # pragma: allowlist secret
                "next": "/scan/",
                "remember_me_supported": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/scan/")
        self._assert_browser_session()

    def test_direct_admin_login_without_marker_keeps_default_persistent_session(self):
        user = self._create_staff_user()

        response = self.client.post(
            f"{reverse('admin:login')}?next=/scan/",
            {
                "username": user.username,
                "password": "pass1234",  # pragma: allowlist secret
                "next": "/scan/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/scan/")
        self._assert_persistent_session()

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
