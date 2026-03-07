from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    Destination,
    Order,
    PublicOrderLink,
    Shipment,
)


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
    def test_critical_english_pages_no_longer_depend_on_runtime_translation(self):
        self.client.force_login(self.staff_user)
        self._activate_english()
        response = self.client.get(reverse("scan:scan_dashboard"))

        self.assertContains(response, "Dashboard")
        self.assertNotContains(response, "Tableau de bord")

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

    def test_portal_dashboard_and_order_create_render_native_english(self):
        self.client.force_login(self.portal_user)
        self._activate_english()

        dashboard = self.client.get(reverse("portal:portal_dashboard"))
        self.assertContains(dashboard, "Association portal")
        self.assertContains(dashboard, "New order")
        self.assertNotContains(dashboard, "Portail association")

        order_create = self.client.get(reverse("portal:portal_order_create"))
        self.assertContains(order_create, "Destination")
        self.assertContains(order_create, "Available parcels")
        self.assertContains(order_create, "Submit order")
        self.assertNotContains(order_create, "Nouvelle commande")

    def test_receive_pages_render_native_english(self):
        self.client.force_login(self.staff_user)
        self._activate_english()

        pallet_response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertContains(pallet_response, "Pallet receiving")
        self.assertContains(pallet_response, "Reception date")
        self.assertNotContains(pallet_response, "R&eacute;ception palette")

        association_response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertContains(association_response, "Association receiving")
        self.assertContains(association_response, "Number of parcels")
        self.assertContains(association_response, "Out-of-format")
        self.assertNotContains(association_response, "R&eacute;ception association")

    def test_scan_stock_and_orders_render_native_english(self):
        self.client.force_login(self.staff_user)
        self._activate_english()

        stock_response = self.client.get(reverse("scan:scan_stock"))
        self.assertContains(stock_response, "Stock view")
        self.assertContains(stock_response, "Search")
        self.assertNotContains(stock_response, "Vue stock")

        stock_update_response = self.client.get(reverse("scan:scan_stock_update"))
        self.assertContains(stock_update_response, "Stock update")
        self.assertContains(stock_update_response, "Product name")
        self.assertNotContains(stock_update_response, "MAJ stock")

        orders_view_response = self.client.get(reverse("scan:scan_orders_view"))
        self.assertContains(orders_view_response, "Order view")
        self.assertContains(orders_view_response, "Track association orders.")
        self.assertNotContains(orders_view_response, "Vue Commande")

        order_response = self.client.get(reverse("scan:scan_order"))
        self.assertContains(order_response, "Orders")
        self.assertContains(order_response, "Existing order")
        self.assertNotContains(order_response, "Commande existante")

        cartons_response = self.client.get(reverse("scan:scan_cartons_ready"))
        self.assertContains(cartons_response, "Parcel view")
        self.assertNotContains(cartons_response, "Vue Colis")

        pack_response = self.client.get(reverse("scan:scan_pack"))
        self.assertContains(pack_response, "Prepare parcels")
        self.assertContains(pack_response, "Parcel format")
        self.assertNotContains(pack_response, "Pr&eacute;paration cartons")

        kits_response = self.client.get(reverse("scan:scan_prepare_kits"))
        self.assertContains(kits_response, "Prepare kits")
        self.assertContains(kits_response, "Kit name")
        self.assertNotContains(kits_response, "Pr&eacute;parer des kits")

    def test_scan_dashboard_faq_and_tracking_render_native_english(self):
        shipment = Shipment.objects.create(
            shipper_name="ASF",
            recipient_name="Association I18N",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

        self.client.force_login(self.staff_user)
        self._activate_english()

        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertContains(dashboard_response, "Dashboard")
        self.assertNotContains(dashboard_response, "Tableau de bord")

        shipments_ready_response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertContains(shipments_ready_response, "Shipments view")
        self.assertNotContains(shipments_ready_response, "Vue Exp&eacute;ditions")

        shipments_tracking_response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertContains(shipments_tracking_response, "Shipment tracking")
        self.assertContains(shipments_tracking_response, "Planned week")
        self.assertNotContains(shipments_tracking_response, "Suivi des exp&eacute;ditions")

        shipment_create_response = self.client.get(reverse("scan:scan_shipment_create"))
        self.assertContains(shipment_create_response, "Create shipment")
        self.assertContains(shipment_create_response, "Save draft")
        self.assertNotContains(shipment_create_response, "Cr&eacute;er une exp&eacute;dition")

        faq_response = self.client.get(reverse("scan:scan_faq"))
        self.assertContains(faq_response, "Access & roles")
        self.assertNotContains(faq_response, "Accès & rôles")

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            tracking_response = self.client.get(
                reverse("scan:scan_shipment_track", args=[shipment.tracking_token])
            )
        self.assertContains(tracking_response, "Shipment tracking")
        self.assertContains(tracking_response, "Current status")
        self.assertNotContains(tracking_response, "Suivi exp&eacute;dition")

        self.client.force_login(self.superuser)
        self._activate_english()
        settings_response = self.client.get(reverse("scan:scan_settings"))
        self.assertContains(settings_response, "Settings")
        self.assertContains(settings_response, "Operational presets")
        self.assertNotContains(settings_response, "Param&egrave;tres")

    def test_forced_password_change_page_renders_native_english(self):
        profile = self.portal_user.association_profile
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password"])
        self._activate_english()

        login_response = self.client.post(
            reverse("portal:portal_login"),
            {
                "identifier": self.portal_user.email,
                "password": "pass1234",
            },
        )

        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.url, reverse("portal:portal_change_password"))

        change_password_response = self.client.get(login_response.url)
        self.assertContains(change_password_response, "Change password")
        self.assertContains(
            change_password_response,
            "Please set a new password to continue.",
        )
        self.assertNotContains(change_password_response, "Changer le mot de passe")

    def test_admin_custom_pages_render_native_english(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Django admin")
        self.assertNotContains(response, "Admin Django")

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

        self.assertContains(response, "Overview")
        self.assertContains(response, "This page describes the full WMS Scan workflow")
        self.assertContains(response, "Reference data")
        self.assertContains(response, "Shipment tracking (Management)")
        self.assertContains(response, "Pallet receiving")
        self.assertContains(response, "Quick filter: Pallet, Association, or All.")
        self.assertContains(response, "A QR code is generated when the shipment is created.")
        self.assertContains(response, "The sync banner indicates that an update is available.")
        self.assertNotContains(response, "Données de référence")
        self.assertNotContains(response, "Filtre rapide : Palette, Association ou Tout.")
        self.assertNotContains(
            response,
            "La bannière de synchro indique qu'une mise à jour est disponible.",
        )
