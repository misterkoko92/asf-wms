from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import AssociationProfile, PublicOrderLink


class LanguageSwitchPauseTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="language-switch-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = user_model.objects.create_superuser(
            username="language-switch-superuser",
            password="pass1234",
            email="language-switch-superuser@example.com",
        )
        self.portal_user = user_model.objects.create_user(
            username="language-switch-portal",
            password="pass1234",
            email="language-switch-portal@example.com",
        )
        association_contact = Contact.objects.create(
            name="Association Pause Langue",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association-language-pause@example.com",
        )
        AssociationProfile.objects.create(
            user=self.portal_user,
            contact=association_contact,
            must_change_password=False,
        )
        self.public_link = PublicOrderLink.objects.create(label="Public language pause")

    def _assert_language_switch_hidden(self, response):
        self.assertNotContains(response, 'name="language"')
        self.assertNotContains(response, 'value="en"')
        self.assertNotContains(response, 'value="fr"')

    def test_language_switch_is_hidden_on_shared_legacy_layouts(self):
        shared_pages = (
            (self.staff_user, reverse("scan:scan_dashboard")),
            (self.portal_user, reverse("portal:portal_dashboard")),
            (self.superuser, reverse("planning:run_list")),
            (self.superuser, reverse("admin:index")),
        )

        for user, url in shared_pages:
            with self.subTest(url=url):
                self.client.force_login(user)
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                self._assert_language_switch_hidden(response)

    def test_language_switch_is_hidden_on_public_and_auth_pages(self):
        public_pages = (
            reverse("portal:portal_login"),
            reverse("portal:portal_forgot_password"),
            reverse("volunteer:login"),
            reverse("volunteer:forgot_password"),
            reverse("scan:scan_public_order", kwargs={"token": self.public_link.token}),
        )

        for url in public_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self._assert_language_switch_hidden(response)
