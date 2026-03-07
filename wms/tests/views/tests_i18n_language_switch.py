from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import AssociationProfile, AssociationRecipient, Destination, Order, PublicOrderLink


class LanguageSwitchI18nTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="i18n-staff",
            password="pass1234",
            is_staff=True,
        )
        self.superuser = user_model.objects.create_superuser(
            username="i18n-superuser",
            password="pass1234",
            email="i18n-superuser@example.com",
        )
        self.portal_user = user_model.objects.create_user(
            username="i18n-portal",
            password="pass1234",
            email="i18n-portal@example.com",
        )

        association_contact = Contact.objects.create(
            name="Association I18N",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email="association-i18n@example.com",
        )
        ContactAddress.objects.create(
            contact=association_contact,
            address_line1="1 Rue Test",
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
        correspondent_contact = Contact.objects.create(
            name="Correspondant I18N",
            contact_type=ContactType.PERSON,
            is_active=True,
            email="correspondant-i18n@example.com",
        )
        destination = Destination.objects.create(
            city="Paris",
            iata_code="I18",
            country="France",
            correspondent_contact=correspondent_contact,
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=association_contact,
            destination=destination,
            name="Destinataire I18N",
            structure_name="Structure I18N",
            address_line1="2 Rue Livraison",
            city="Paris",
            country="France",
            is_delivery_contact=True,
            is_active=True,
        )
        self.public_link = PublicOrderLink.objects.create(label="Public I18N")
        Order.objects.create(
            public_link=self.public_link,
            shipper_name="ASF",
            recipient_name="Destinataire I18N",
            destination_address="2 Rue Livraison\n75001 Paris\nFrance",
            destination_country="France",
        )

    def _activate_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def test_set_language_route_exists_and_updates_cookie(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("set_language"),
            {
                "language": "en",
                "next": reverse("scan:scan_dashboard"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_dashboard"))
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value,
            "en",
        )

    def test_language_switch_is_visible_on_scan_portal_and_admin(self):
        self.client.force_login(self.staff_user)
        scan_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertContains(scan_response, 'name="language"')
        self.assertContains(scan_response, 'value="en"')
        self.assertContains(scan_response, 'value="fr"')

        self.client.force_login(self.portal_user)
        portal_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertContains(portal_response, 'name="language"')
        self.assertContains(portal_response, 'value="en"')
        self.assertContains(portal_response, 'value="fr"')

        self.client.force_login(self.superuser)
        admin_response = self.client.get(reverse("admin:index"))
        self.assertContains(admin_response, 'name="language"')
        self.assertContains(admin_response, 'value="en"')
        self.assertContains(admin_response, 'value="fr"')

    def test_scan_and_portal_pages_render_english_when_language_is_en(self):
        self.client.force_login(self.staff_user)
        self._activate_english()
        scan_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertContains(scan_response, "Dashboard")
        self.assertContains(scan_response, "Log out")
        self.assertNotContains(scan_response, "Tableau de bord")

        self.client.force_login(self.portal_user)
        self._activate_english()
        portal_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertContains(portal_response, "Association portal")
        self.assertContains(portal_response, "Orders")
        self.assertContains(portal_response, "New order")
        self.assertNotContains(portal_response, "Portail association")

    def test_login_and_receiving_pages_render_natural_english_labels(self):
        self._activate_english()
        login_response = self.client.get(reverse("portal:portal_login"))
        self.assertContains(login_response, "Association login")
        self.assertContains(login_response, "Use your email and password.")
        self.assertContains(login_response, "Request an account")
        self.assertContains(login_response, "Forgot password / First login")
        self.assertContains(login_response, "Sign in")

        self.client.force_login(self.staff_user)
        self._activate_english()
        pallet_response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertContains(pallet_response, "Pallet receiving")
        self.assertContains(pallet_response, "Reception date")
        self.assertContains(pallet_response, "Number of pallets")
        self.assertContains(pallet_response, "Save pallet receiving")
        self.assertContains(pallet_response, "Add donor")
        self.assertContains(pallet_response, "Add carrier")

        association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertContains(association_response, "Association receiving")
        self.assertContains(association_response, "Number of parcels")
        self.assertContains(association_response, "Out-of-format")
        self.assertContains(association_response, "Save association receiving")

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_runtime_translation_can_be_disabled(self):
        self.client.force_login(self.staff_user)
        self._activate_english()
        response = self.client.get(reverse("scan:scan_receive_pallet"))

        self.assertContains(response, "R&eacute;ception palette")
        self.assertNotContains(response, "Pallet receiving")

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_public_auth_pages_render_native_english(self):
        self._activate_english()

        login_response = self.client.get(reverse("portal:portal_login"))
        self.assertContains(login_response, "Association login")
        self.assertContains(login_response, "Use your email and password.")
        self.assertNotContains(login_response, "Connexion association")

        recovery_response = self.client.get(reverse("portal:portal_forgot_password"))
        self.assertContains(recovery_response, "Forgot password / First login")
        self.assertContains(
            recovery_response,
            "Enter your email to receive a link to set or reset your password.",
        )
        self.assertContains(recovery_response, "Back to sign in")

        set_password_response = self.client.get(
            reverse("portal:portal_set_password", args=["a", "invalid-token"])
        )
        self.assertContains(set_password_response, "Set a password")
        self.assertContains(set_password_response, "Invalid or expired link. Contact ASF.")

        account_request_response = self.client.get(reverse("portal:portal_account_request"))
        self.assertContains(account_request_response, "Account creation")
        self.assertContains(
            account_request_response,
            "Choose your profile, then submit your request. An ASF administrator must validate the account.",
        )
        self.assertContains(account_request_response, "Back to the portal")

        public_order_response = self.client.get(
            reverse("scan:scan_public_order", kwargs={"token": self.public_link.token})
        )
        self.assertContains(public_order_response, "Order request")
        self.assertContains(public_order_response, "Create an account")
        self.assertContains(public_order_response, "Submit order")

    def test_language_switch_is_present_on_standalone_pages(self):
        login_response = self.client.get(reverse("portal:portal_login"))
        self.assertContains(login_response, 'name="language"')
        self.assertContains(login_response, 'value="en"')
        self.assertContains(login_response, 'value="fr"')

        public_order_response = self.client.get(
            reverse("scan:scan_public_order", kwargs={"token": self.public_link.token})
        )
        self.assertContains(public_order_response, 'name="language"')
        self.assertContains(public_order_response, 'value="en"')
        self.assertContains(public_order_response, 'value="fr"')

    def test_scan_faq_page_uses_english_section_titles(self):
        self.client.force_login(self.staff_user)
        self._activate_english()
        response = self.client.get(reverse("scan:scan_faq"))

        self.assertContains(response, "Access &amp; roles")
        self.assertContains(response, "Reference data")
        self.assertContains(response, "Shipment tracking (Management)")
        self.assertContains(response, "Documents &amp; labels")
        self.assertContains(response, "Pallet receiving")
        self.assertNotContains(response, "Acc&egrave;s &amp; r&ocirc;les")
        self.assertNotContains(response, "Donn&eacute;es de r&eacute;f&eacute;rence")
