from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode

from contacts.models import Contact, ContactAddress, ContactType
from contacts.querysets import contacts_with_tags
from contacts.tagging import TAG_RECIPIENT, TAG_SHIPPER
from wms.forms import ScanShipmentForm
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    AssociationProfile,
    AssociationPortalContact,
    AssociationRecipient,
    Destination,
    DocumentReviewStatus,
    Location,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderReviewStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    Warehouse,
)
from wms import portal_helpers
from wms.services import StockError


class PortalBaseTestCase(TestCase):
    def _create_association_contact(self, name, with_address=True):
        contact = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email=f"{name.lower().replace(' ', '')}@example.com",
        )
        if with_address:
            ContactAddress.objects.create(
                contact=contact,
                address_line1="1 Rue Test",
                city="Paris",
                postal_code="75001",
                country="France",
                is_default=True,
            )
        return contact

    def _create_portal_user(self, username, email, password="pass1234", *, active=True):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            is_active=active,
        )

    def _create_profile(self, user, *, must_change_password=False, with_address=True):
        contact = self._create_association_contact(
            f"Association {user.username}",
            with_address=with_address,
        )
        profile = AssociationProfile.objects.create(
            user=user,
            contact=contact,
            must_change_password=must_change_password,
        )
        return profile

    def _create_destination(self, *, city="Paris", country="France"):
        suffix = Destination.objects.count() + 1
        correspondent = Contact.objects.create(
            name=f"Correspondant {suffix}",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city=city,
            iata_code=f"T{suffix:03d}",
            country=country,
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_delivery_recipient(
        self,
        profile,
        *,
        city="Paris",
        country="France",
        structure_name="Structure Test",
    ):
        destination = self._create_destination(city=city, country=country)
        return AssociationRecipient.objects.create(
            association_contact=profile.contact,
            destination=destination,
            name=structure_name,
            structure_name=structure_name,
            address_line1="1 Rue Réception",
            city=city,
            country=country,
            is_delivery_contact=True,
            is_active=True,
        )


class PortalHelpersTests(PortalBaseTestCase):
    def test_get_contact_address_returns_none_without_contact(self):
        self.assertIsNone(portal_helpers.get_contact_address(None))

    def test_get_contact_address_uses_addresses_manager_without_effective_method(self):
        default_address = object()
        fallback_address = object()
        filtered = mock.MagicMock()
        filtered.first.return_value = default_address
        addresses = mock.MagicMock()
        addresses.filter.return_value = filtered
        addresses.first.return_value = fallback_address
        contact = SimpleNamespace(addresses=addresses)
        self.assertIs(portal_helpers.get_contact_address(contact), default_address)
        addresses.filter.assert_called_once_with(is_default=True)
        addresses.first.assert_not_called()

    def test_get_contact_address_falls_back_to_first_address_when_no_default(self):
        fallback_address = object()
        filtered = mock.MagicMock()
        filtered.first.return_value = None
        addresses = mock.MagicMock()
        addresses.filter.return_value = filtered
        addresses.first.return_value = fallback_address
        contact = SimpleNamespace(addresses=addresses)
        self.assertIs(portal_helpers.get_contact_address(contact), fallback_address)
        addresses.first.assert_called_once()

    def test_get_association_profile_returns_none_for_anonymous_user(self):
        self.assertIsNone(portal_helpers.get_association_profile(AnonymousUser()))

    @override_settings(SITE_BASE_URL="https://portal.example.org/base/")
    def test_build_public_base_url_prefers_site_setting(self):
        request = RequestFactory().get("/ignored")
        self.assertEqual(
            portal_helpers.build_public_base_url(request),
            "https://portal.example.org/base",
        )

    @override_settings(SITE_BASE_URL="")
    def test_build_public_base_url_uses_request_absolute_uri(self):
        request = RequestFactory().get("/portal/account/")
        self.assertEqual(
            portal_helpers.build_public_base_url(request),
            "http://testserver",
        )


class PortalAuthViewsTests(PortalBaseTestCase):
    def setUp(self):
        self.login_url = reverse("portal:portal_login")
        self.logout_url = reverse("portal:portal_logout")
        self.change_password_url = reverse("portal:portal_change_password")
        self.dashboard_url = reverse("portal:portal_dashboard")

    def _set_password_url(self, user, token=None):
        token = token or default_token_generator.make_token(user)
        uidb64 = urlsafe_base64_encode(str(user.pk).encode())
        return reverse("portal:portal_set_password", args=[uidb64, token])

    def test_portal_login_redirects_authenticated_user_with_profile(self):
        user = self._create_portal_user("portal-auth-a", "a@example.com")
        self._create_profile(user)
        self.client.force_login(user)
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.dashboard_url)

    def test_portal_login_requires_identifier_and_password(self):
        response = self.client.post(self.login_url, {"identifier": "", "password": ""})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Email et mot de passe requis.", response.context["errors"])

    def test_portal_login_get_shows_account_request_link(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("portal:portal_account_request"))
        self.assertContains(response, "Demander un compte")

    def test_portal_login_rejects_invalid_credentials(self):
        response = self.client.post(
            self.login_url,
            {"identifier": "unknown@example.com", "password": "bad"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Identifiants invalides.", response.context["errors"])

    def test_portal_login_rejects_inactive_account(self):
        user = self._create_portal_user(
            "portal-auth-inactive",
            "inactive@example.com",
            active=False,
        )
        with mock.patch("wms.views_portal_auth.authenticate", return_value=user):
            response = self.client.post(
                self.login_url,
                {"identifier": user.email, "password": "pass1234"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Compte inactif.", response.context["errors"])

    def test_portal_login_rejects_user_without_association_profile(self):
        user = self._create_portal_user("portal-auth-b", "b@example.com")
        response = self.client.post(
            self.login_url,
            {"identifier": user.email, "password": "pass1234"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Compte non activé par ASF.", response.context["errors"])

    def test_portal_login_redirects_to_change_password_when_forced(self):
        user = self._create_portal_user("portal-auth-c", "c@example.com")
        self._create_profile(user, must_change_password=True)
        response = self.client.post(
            self.login_url,
            {"identifier": user.email, "password": "pass1234"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.change_password_url)

    def test_portal_login_redirects_to_next_url_when_present(self):
        user = self._create_portal_user("portal-auth-d", "d@example.com")
        self._create_profile(user)
        next_url = reverse("portal:portal_account")
        response = self.client.post(
            self.login_url,
            {
                "identifier": user.email,
                "password": "pass1234",
                "next": next_url,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)

    def test_portal_login_ignorés_external_next_url(self):
        user = self._create_portal_user("portal-auth-next", "next@example.com")
        self._create_profile(user)
        response = self.client.post(
            self.login_url,
            {
                "identifier": user.email,
                "password": "pass1234",
                "next": "https://evil.example.org/phishing",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.dashboard_url)

    def test_portal_login_get_ignorés_external_next_url_in_context(self):
        response = self.client.get(
            self.login_url,
            {"next": "https://evil.example.org/phishing"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["next"], "")

    def test_portal_logout_redirects_to_login(self):
        user = self._create_portal_user("portal-auth-e", "e@example.com")
        self.client.force_login(user)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.login_url)

    def test_portal_set_password_rejects_invalid_token(self):
        user = self._create_portal_user("portal-auth-f", "f@example.com")
        url = self._set_password_url(user, token="invalid-token")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["invalid"])

    def test_portal_set_password_rejects_malformed_uid(self):
        url = reverse("portal:portal_set_password", args=["a", "invalid-token"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["invalid"])

    def test_portal_set_password_get_renders_form_for_valid_token(self):
        user = self._create_portal_user("portal-auth-g", "g@example.com")
        url = self._set_password_url(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["invalid"])
        self.assertIn("form", response.context)

    def test_portal_set_password_post_updates_password_and_profile(self):
        user = self._create_portal_user("portal-auth-h", "h@example.com")
        profile = self._create_profile(user, must_change_password=True)
        url = self._set_password_url(user)
        response = self.client.post(
            url,
            {
                "new_password1": "NewPass1234!",
                "new_password2": "NewPass1234!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.dashboard_url)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(profile.must_change_password)
        self.assertTrue(user.check_password("NewPass1234!"))

    def test_portal_change_password_updates_password_and_clears_flag(self):
        user = self._create_portal_user("portal-auth-i", "i@example.com")
        profile = self._create_profile(user, must_change_password=True)
        self.client.force_login(user)

        get_response = self.client.get(self.change_password_url)
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(
            self.change_password_url,
            {
                "new_password1": "OtherPass1234!",
                "new_password2": "OtherPass1234!",
            },
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, self.dashboard_url)
        profile.refresh_from_db()
        user.refresh_from_db()
        self.assertFalse(profile.must_change_password)
        self.assertTrue(user.check_password("OtherPass1234!"))


class PortalOrdersViewsTests(PortalBaseTestCase):
    def setUp(self):
        self.user = self._create_portal_user(
            "portal-orders",
            "orders@example.com",
        )
        self.profile = self._create_profile(self.user, with_address=True)
        self.delivery_recipient = self._create_delivery_recipient(self.profile)
        self.destination = self.delivery_recipient.destination
        self.client.force_login(self.user)
        self.dashboard_url = reverse("portal:portal_dashboard")
        self.order_create_url = reverse("portal:portal_order_create")
        self.product = Product.objects.create(name="Produit Portail")
        self.product_options = [
            {"id": self.product.id, "name": self.product.name, "available_stock": 5}
        ]
        self.product_by_id = {self.product.id: self.product}
        self.available_by_id = {self.product.id: 5}

    def _order(self, *, review_status=OrderReviewStatus.PENDING, contact=None):
        contact = contact or self.profile.contact
        return Order.objects.create(
            association_contact=contact,
            review_status=review_status,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=contact.name,
            destination_address="1 Rue Test\n75001 Paris\nFrance",
            destination_country="France",
        )

    def test_portal_dashboard_lists_only_association_orders(self):
        own_order = self._order()
        other_contact = self._create_association_contact("Association Other", with_address=True)
        other_order = self._order(contact=other_contact)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        orders = list(response.context["orders"])
        self.assertIn(own_order, orders)
        self.assertNotIn(other_order, orders)

    def test_portal_dashboard_displays_shipment_dates_and_escale(self):
        destination = self._create_destination(city="Abidjan", country="Cote d'Ivoire")
        shipment = Shipment.objects.create(
            shipper_name="ASF",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="Cote d'Ivoire",
            destination=destination,
        )
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.BOARDING_OK,
            actor_name="Agent",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            actor_name="Agent",
            actor_structure="ASF",
        )
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            actor_name="Agent",
            actor_structure="ASF",
        )
        reviewed_at = timezone.now()
        Order.objects.create(
            association_contact=self.profile.contact,
            review_status=OrderReviewStatus.APPROVED,
            reviewed_at=reviewed_at,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=self.profile.contact.name,
            destination_address="1 Rue Test\n75001 Paris\nFrance",
            destination_country="France",
            shipment=shipment,
        )

        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Abidjan", html)
        self.assertIn(reviewed_at.strftime("%d/%m/%Y"), html)

    def test_portal_dashboard_redirects_when_delivery_contact_missing(self):
        AssociationRecipient.objects.filter(association_contact=self.profile.contact).delete()
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('portal:portal_recipients')}?blocked=missing_delivery_contact",
        )

    def test_portal_order_create_get_renders(self):
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            response = self.client.get(self.order_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("destination_options", response.context)
        self.assertIn("recipient_options", response.context)

    def test_portal_order_create_filters_recipient_options_by_destination(self):
        other_destination = self._create_destination(city="Abidjan", country="Cote d'Ivoire")
        other_recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=other_destination,
            name="Recipient Other",
            address_line1="20 Rue Other",
            city="Abidjan",
            country="Cote d'Ivoire",
            is_active=True,
        )
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=([], {}, {}),
            ):
                response = self.client.post(
                    self.order_create_url,
                    {
                        "destination_id": str(self.destination.id),
                        "recipient_id": "",
                        "notes": "",
                    },
                )
        self.assertEqual(response.status_code, 200)
        recipient_ids = {
            str(option["id"])
            for option in response.context["recipient_options"]
            if option["id"] != "self"
        }
        self.assertIn(str(self.delivery_recipient.id), recipient_ids)
        self.assertNotIn(str(other_recipient.id), recipient_ids)

    def test_portal_order_create_post_reports_missing_recipient_and_products(self):
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=([], {}, {}),
            ):
                response = self.client.post(
                    self.order_create_url,
                    {"destination_id": "", "recipient_id": "", "notes": ""},
                )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Destination requise.", response.context["errors"])
        self.assertIn("Destinataire requis.", response.context["errors"])
        self.assertIn("Ajoutez au moins un produit.", response.context["errors"])

    def test_portal_order_create_post_self_requires_address(self):
        self.profile.contact.addresses.all().delete()
        line_items = [(self.product, 1)]
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=(line_items, {}, {}),
            ):
                response = self.client.post(
                    self.order_create_url,
                    {
                        "destination_id": str(self.destination.id),
                        "recipient_id": "self",
                        "notes": "",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Adresse association manquante.", response.context["errors"])

    def test_portal_order_create_post_invalid_recipient(self):
        line_items = [(self.product, 1)]
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=(line_items, {}, {}),
            ):
                response = self.client.post(
                    self.order_create_url,
                    {
                        "destination_id": str(self.destination.id),
                        "recipient_id": "999999",
                        "notes": "",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Destinataire non disponible pour cette destination.",
            response.context["errors"],
        )

    def test_portal_order_create_post_with_recipient_uses_recipient_destination(self):
        destination = self._create_destination(city="Lyon", country="France")
        recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=destination,
            name="Recipient External",
            address_line1="10 Rue C",
            address_line2="Bat A",
            postal_code="69000",
            city="Lyon",
            country="",
            is_active=True,
        )
        line_items = [(self.product, 1)]
        fake_order = SimpleNamespace(id=456)
        synced_recipient_contact = Contact.objects.create(
            name="Synced Recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=(line_items, {}, {}),
            ):
                with mock.patch(
                    "wms.views_portal_orders.sync_association_recipient_to_contact",
                    return_value=synced_recipient_contact,
                ):
                    with mock.patch(
                        "wms.views_portal_orders.create_portal_order",
                        return_value=fake_order,
                    ) as create_order_mock:
                        with mock.patch(
                            "wms.views_portal_orders.send_portal_order_notifications"
                        ):
                            response = self.client.post(
                                self.order_create_url,
                                {
                                    "destination_id": str(destination.id),
                                    "recipient_id": str(recipient.id),
                                    "notes": "External",
                                },
                            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("portal:portal_order_detail", kwargs={"order_id": 456}),
        )
        self.assertEqual(create_order_mock.call_count, 1)
        kwargs = create_order_mock.call_args.kwargs
        self.assertEqual(kwargs["recipient_name"], recipient.name)
        self.assertEqual(kwargs["recipient_contact"], synced_recipient_contact)
        self.assertEqual(kwargs["destination_city"], "Lyon")
        self.assertEqual(kwargs["destination_country"], "France")
        self.assertEqual(
            kwargs["destination_address"],
            "10 Rue C\nBat A\n69000 Lyon\nFrance",
        )

    def test_portal_order_create_post_handles_stock_error(self):
        line_items = [(self.product, 1)]
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=(line_items, {}, {}),
            ):
                with mock.patch(
                    "wms.views_portal_orders.create_portal_order",
                    side_effect=StockError("Stock insuffisant"),
                ):
                    response = self.client.post(
                        self.order_create_url,
                        {
                            "destination_id": str(self.destination.id),
                            "recipient_id": "self",
                            "notes": "",
                        },
                    )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Stock insuffisant", response.context["errors"])

    def test_portal_order_create_post_success_redirects_to_detail(self):
        line_items = [(self.product, 1)]
        fake_order = SimpleNamespace(id=123)
        with mock.patch(
            "wms.views_portal_orders.build_product_selection_data",
            return_value=(self.product_options, self.product_by_id, self.available_by_id),
        ):
            with mock.patch(
                "wms.views_portal_orders.build_order_line_items",
                return_value=(line_items, {}, {}),
            ):
                with mock.patch(
                    "wms.views_portal_orders.create_portal_order",
                    return_value=fake_order,
                ) as create_order_mock:
                    with mock.patch(
                        "wms.views_portal_orders.send_portal_order_notifications"
                    ) as notify_mock:
                        response = self.client.post(
                            self.order_create_url,
                            {
                                "destination_id": str(self.destination.id),
                                "recipient_id": "self",
                                "notes": "OK",
                            },
                        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("portal:portal_order_detail", kwargs={"order_id": 123}),
        )
        create_order_mock.assert_called_once()
        notify_mock.assert_called_once()

    def test_portal_to_scan_flow_prefills_shipment_after_admin_validation(self):
        warehouse = Warehouse.objects.create(name="Portal Flow Warehouse")
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="PORTAL-FLOW-001",
            name="Produit Flux Portail",
            default_location=location,
            qr_code_image="qr_codes/portal_flow.png",
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-PORTAL-FLOW",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=50,
            location=location,
        )

        with mock.patch("wms.views_portal_orders.send_portal_order_notifications"):
            portal_response = self.client.post(
                self.order_create_url,
                {
                    "destination_id": str(self.destination.id),
                    "recipient_id": str(self.delivery_recipient.id),
                    f"product_{product.id}_qty": "2",
                    "notes": "Flux portail vers scan",
                },
            )
        self.assertEqual(portal_response.status_code, 302)

        order = (
            Order.objects.filter(association_contact=self.profile.contact)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(order)
        self.assertEqual(order.review_status, OrderReviewStatus.PENDING)
        self.assertIsNotNone(order.shipment_id)
        self.assertIsNotNone(order.recipient_contact_id)
        self.assertEqual(order.shipper_contact_id, self.profile.contact_id)

        staff_user = self._create_portal_user("scan-staff", "scan-staff@example.com")
        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        self.client.force_login(staff_user)

        review_response = self.client.post(
            reverse("scan:scan_orders_view"),
            {
                "action": "update_status",
                "order_id": str(order.id),
                "review_status": OrderReviewStatus.APPROVED,
            },
        )
        self.assertEqual(review_response.status_code, 302)

        create_response = self.client.post(
            reverse("scan:scan_orders_view"),
            {
                "action": "create_shipment",
                "order_id": str(order.id),
            },
        )
        self.assertEqual(create_response.status_code, 302)

        order.refresh_from_db()
        self.assertIsNotNone(order.shipment_id)
        self.assertEqual(
            create_response.url,
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": order.shipment_id}),
        )

        shipment_response = self.client.get(create_response.url)
        self.assertEqual(shipment_response.status_code, 200)
        form = shipment_response.context["form"]
        self.assertEqual(form.initial["destination"], self.destination.id)
        self.assertEqual(form.initial["shipper_contact"], self.profile.contact_id)
        self.assertEqual(form.initial["recipient_contact"], order.recipient_contact_id)

        self.assertEqual(
            shipment_response.context["line_values"],
            [
                {
                    "carton_id": "",
                    "product_code": "PORTAL-FLOW-001",
                    "quantity": "2",
                }
            ],
        )
        self.assertEqual(
            shipment_response.context["products_json"],
            [
                {
                    "id": product.id,
                    "name": product.name,
                    "sku": product.sku,
                    "barcode": product.barcode,
                    "ean": product.ean,
                    "brand": product.brand,
                    "default_location_id": product.default_location_id,
                    "storage_conditions": product.storage_conditions,
                    "weight_g": product.weight_g,
                    "volume_cm3": product.volume_cm3,
                    "length_cm": product.length_cm,
                    "width_cm": product.width_cm,
                    "height_cm": product.height_cm,
                    "available_stock": 2,
                }
            ],
        )

    def test_portal_order_detail_get_renders_and_flags_upload_permission(self):
        order = self._order(review_status=OrderReviewStatus.APPROVED)
        order.lines.create(product=self.product, quantity=2)
        response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_upload_docs"])

    def test_portal_order_detail_is_scoped_to_association(self):
        other_contact = self._create_association_contact("Association X", with_address=True)
        order = self._order(contact=other_contact)
        response = self.client.get(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id})
        )
        self.assertEqual(response.status_code, 404)

    def test_portal_order_detail_blocks_upload_when_order_not_approved(self):
        order = self._order(review_status=OrderReviewStatus.PENDING)
        response = self.client.post(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
            {"action": "upload_doc"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 0)

    def test_portal_order_detail_reports_upload_validation_error(self):
        order = self._order(review_status=OrderReviewStatus.APPROVED)
        with mock.patch(
            "wms.views_portal_orders.validate_document_upload",
            return_value=(None, "Type de document invalide."),
        ):
            response = self.client.post(
                reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
                {"action": "upload_doc"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 0)

    def test_portal_order_detail_uploads_document_when_valid(self):
        order = self._order(review_status=OrderReviewStatus.APPROVED)
        uploaded = SimpleUploadedFile("attestation.pdf", b"pdf-content")
        with mock.patch(
            "wms.views_portal_orders.validate_document_upload",
            return_value=((OrderDocumentType.OTHER, uploaded), None),
        ):
            response = self.client.post(
                reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
                {"action": "upload_doc"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 1)
        document = OrderDocument.objects.get(order=order)
        self.assertEqual(document.doc_type, OrderDocumentType.OTHER)
        self.assertEqual(document.status, DocumentReviewStatus.PENDING)

    def test_portal_order_detail_uploads_documents_by_type_rows(self):
        order = self._order(review_status=OrderReviewStatus.APPROVED)
        uploaded = SimpleUploadedFile("invoice.pdf", b"pdf-content")
        response = self.client.post(
            reverse("portal:portal_order_detail", kwargs={"order_id": order.id}),
            {
                "action": "upload_docs",
                "doc_file_invoice": uploaded,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.documents.count(), 1)
        document = OrderDocument.objects.get(order=order)
        self.assertEqual(document.doc_type, OrderDocumentType.INVOICE)


class PortalAccountViewsTests(PortalBaseTestCase):
    def setUp(self):
        self.user = self._create_portal_user("portal-account", "account@example.com")
        self.profile = self._create_profile(self.user, with_address=True)
        self.client.force_login(self.user)
        self.recipients_url = reverse("portal:portal_recipients")
        self.account_url = reverse("portal:portal_account")
        self.account_request_url = reverse("portal:portal_account_request")
        self.destination = self._create_destination(city="Lyon", country="France")

    def test_portal_recipients_get_lists_active_recipients(self):
        active = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            name="Recipient A",
            address_line1="1 Rue A",
            city="Paris",
            country="France",
            is_active=True,
        )
        AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            name="Recipient B",
            address_line1="1 Rue B",
            city="Paris",
            country="France",
            is_active=False,
        )
        response = self.client.get(self.recipients_url)
        self.assertEqual(response.status_code, 200)
        recipients = list(response.context["recipients"])
        self.assertEqual(recipients, [active])

    def test_portal_recipients_post_validates_required_fields(self):
        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": "",
                "structure_name": "",
                "address_line1": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Escale de livraison requise.", response.context["errors"])
        self.assertIn("Nom de la structure requis.", response.context["errors"])
        self.assertIn("Adresse requise.", response.context["errors"])
        self.assertEqual(AssociationRecipient.objects.count(), 0)

    def test_portal_recipients_post_creates_recipient(self):
        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(self.destination.id),
                "structure_name": "Structure C",
                "contact_title": "mrs",
                "contact_last_name": "Martin",
                "contact_first_name": "Claire",
                "emails": "recipient@example.com; second@example.com",
                "phones": "+33102030405; +33611121314",
                "address_line1": "2 Rue C",
                "address_line2": "",
                "postal_code": "75002",
                "city": "Paris",
                "country": "France",
                "notes": "Notes",
                "notify_deliveries": "1",
                "is_delivery_contact": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipients_url)
        self.assertEqual(AssociationRecipient.objects.count(), 1)
        recipient = AssociationRecipient.objects.get()
        self.assertEqual(recipient.structure_name, "Structure C")
        self.assertEqual(recipient.contact_last_name, "Martin")
        self.assertEqual(recipient.email, "recipient@example.com")
        self.assertEqual(recipient.phone, "+33102030405")
        self.assertTrue(recipient.notify_deliveries)
        self.assertTrue(recipient.is_delivery_contact)

        synced_contact = contacts_with_tags(TAG_RECIPIENT).filter(name="Structure C").first()
        self.assertIsNotNone(synced_contact)
        self.assertTrue(
            synced_contact.linked_shippers.filter(pk=self.profile.contact_id).exists()
        )
        self.assertTrue(synced_contact.destinations.filter(pk=self.destination.id).exists())
        self.assertTrue(
            self.profile.contact.destinations.filter(pk=self.destination.id).exists()
        )
        self.assertTrue(
            contacts_with_tags(TAG_SHIPPER).filter(pk=self.profile.contact_id).exists()
        )

        form = ScanShipmentForm(
            data={
                "destination": str(self.destination.id),
                "shipper_contact": str(self.profile.contact_id),
            },
            destination_id=str(self.destination.id),
        )
        self.assertIn(
            synced_contact.id,
            set(form.fields["recipient_contact"].queryset.values_list("id", flat=True)),
        )

    def test_portal_recipients_get_with_edit_prefills_form(self):
        recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=self.destination,
            name="Structure Edit",
            structure_name="Structure Edit",
            contact_title="mr",
            contact_last_name="Durand",
            contact_first_name="Marc",
            address_line1="10 Rue Edit",
            city="Paris",
            country="France",
            is_active=True,
        )
        response = self.client.get(f"{self.recipients_url}?edit={recipient.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["editing_recipient"], recipient)
        self.assertEqual(response.context["form_data"]["structure_name"], "Structure Edit")
        self.assertEqual(response.context["form_data"]["contact_last_name"], "Durand")

    def test_portal_recipients_post_updates_recipient(self):
        recipient = AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=self.destination,
            name="Structure Before",
            structure_name="Structure Before",
            contact_title="mr",
            contact_last_name="Durand",
            contact_first_name="Marc",
            address_line1="10 Rue Before",
            city="Paris",
            country="France",
            is_active=True,
        )
        response = self.client.post(
            self.recipients_url,
            {
                "action": "update_recipient",
                "recipient_id": str(recipient.id),
                "destination_id": str(self.destination.id),
                "structure_name": "Structure After",
                "contact_title": "gen",
                "contact_last_name": "Martin",
                "contact_first_name": "Claire",
                "emails": "after@example.com",
                "phones": "+33123456789",
                "address_line1": "20 Rue After",
                "address_line2": "",
                "postal_code": "75003",
                "city": "Paris",
                "country": "France",
                "notes": "",
                "notify_deliveries": "1",
                "is_delivery_contact": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.recipients_url)
        recipient.refresh_from_db()
        self.assertEqual(recipient.structure_name, "Structure After")
        self.assertEqual(recipient.contact_title, "gen")
        self.assertEqual(recipient.contact_last_name, "Martin")
        self.assertEqual(recipient.email, "after@example.com")
        self.assertEqual(recipient.phone, "+33123456789")
        self.assertTrue(recipient.notify_deliveries)
        self.assertTrue(recipient.is_delivery_contact)
        self.assertEqual(
            Contact.objects.filter(
                notes__startswith=f"[Portail association][recipient_id={recipient.id}]"
            ).count(),
            1,
        )

    def test_portal_recipients_get_exposes_extended_contact_titles(self):
        response = self.client.get(self.recipients_url)
        self.assertEqual(response.status_code, 200)
        choices = dict(response.context["contact_title_choices"])
        self.assertEqual(choices["pere"], "Père")
        self.assertEqual(choices["gen"], "Général")

    def test_portal_recipients_get_shows_blocking_popup_message(self):
        response = self.client.get(
            f"{self.recipients_url}?blocked=missing_delivery_contact"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Compte bloqué", response.content.decode())

    def test_portal_account_get_renders(self):
        response = self.client.get(self.account_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["association"], self.profile.contact)

    def test_portal_account_updates_profile_and_contacts(self):
        response = self.client.post(
            self.account_url,
            {
                "action": "update_profile",
                "association_name": "Association Renamed",
                "association_email": "association-renamed@example.com",
                "association_phone": "0601020304",
                "address_line1": "10 Rue Update",
                "address_line2": "Batiment B",
                "postal_code": "75011",
                "city": "Paris",
                "country": "France",
                "contact_count": "2",
                "contact_0_title": "mr",
                "contact_0_last_name": "Durand",
                "contact_0_first_name": "Marc",
                "contact_0_phone": "0600000000",
                "contact_0_email": "admin@example.com",
                "contact_0_is_administrative": "1",
                "contact_1_title": "mrs",
                "contact_1_last_name": "Martin",
                "contact_1_first_name": "Claire",
                "contact_1_phone": "0600000001",
                "contact_1_email": "billing@example.com",
                "contact_1_is_billing": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.account_url)

        self.profile.refresh_from_db()
        self.profile.contact.refresh_from_db()
        self.assertEqual(self.profile.contact.name, "Association Renamed")
        self.assertEqual(self.profile.contact.email, "association-renamed@example.com")
        self.assertEqual(self.profile.contact.phone, "0601020304")
        self.assertEqual(self.profile.notification_emails, "admin@example.com,billing@example.com")

        address = self.profile.contact.get_effective_address()
        self.assertIsNotNone(address)
        self.assertEqual(address.address_line1, "10 Rue Update")
        self.assertEqual(address.city, "Paris")

        contacts = list(self.profile.portal_contacts.order_by("position"))
        self.assertEqual(len(contacts), 2)
        self.assertEqual(contacts[0].email, "admin@example.com")
        self.assertTrue(contacts[0].is_administrative)
        self.assertEqual(contacts[1].email, "billing@example.com")
        self.assertTrue(contacts[1].is_billing)

    def test_portal_account_update_profile_requires_contact_type(self):
        response = self.client.post(
            self.account_url,
            {
                "action": "update_profile",
                "association_name": "Association X",
                "association_email": "x@example.com",
                "association_phone": "0601020304",
                "address_line1": "10 Rue Update",
                "address_line2": "",
                "postal_code": "75011",
                "city": "Paris",
                "country": "France",
                "contact_count": "1",
                "contact_0_title": "mr",
                "contact_0_last_name": "Durand",
                "contact_0_first_name": "Marc",
                "contact_0_phone": "0600000000",
                "contact_0_email": "admin@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Ligne 1: cochez au moins un type.",
            response.context["account_form_errors"],
        )
        self.assertEqual(AssociationPortalContact.objects.count(), 0)

    def test_portal_account_updates_notification_emails(self):
        response = self.client.post(
            self.account_url,
            {"action": "update_notifications", "notification_emails": "a@x.com,b@x.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.account_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.notification_emails, "a@x.com,b@x.com")

    def test_portal_account_upload_doc_reports_validation_error(self):
        with mock.patch(
            "wms.views_portal_account.validate_document_upload",
            return_value=(None, "Type de document invalide."),
        ):
            response = self.client.post(
                self.account_url,
                {"action": "upload_account_doc"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.account_url)
        self.assertEqual(AccountDocument.objects.count(), 0)

    def test_portal_account_upload_doc_creates_document(self):
        uploaded = SimpleUploadedFile("statuts.pdf", b"pdf-content")
        with mock.patch(
            "wms.views_portal_account.validate_document_upload",
            return_value=((AccountDocumentType.OTHER, uploaded), None),
        ):
            response = self.client.post(
                self.account_url,
                {"action": "upload_account_doc"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.account_url)
        self.assertEqual(AccountDocument.objects.count(), 1)
        document = AccountDocument.objects.get()
        self.assertEqual(document.doc_type, AccountDocumentType.OTHER)
        self.assertEqual(document.status, DocumentReviewStatus.PENDING)

    def test_portal_account_upload_docs_creates_documents_by_type_row(self):
        response = self.client.post(
            self.account_url,
            {
                "action": "upload_account_docs",
                "doc_file_statutes": SimpleUploadedFile("statuts.pdf", b"pdf-content"),
                "doc_file_other": SimpleUploadedFile("other.pdf", b"pdf-content"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.account_url)
        docs = list(AccountDocument.objects.order_by("doc_type"))
        self.assertEqual(len(docs), 2)
        self.assertEqual(
            {doc.doc_type for doc in docs},
            {AccountDocumentType.STATUTES, AccountDocumentType.OTHER},
        )

    def test_portal_account_request_delegates_to_handler(self):
        with mock.patch(
            "wms.views_portal_account.handle_account_request_form",
            return_value=HttpResponse("ok"),
        ) as handler_mock:
            response = self.client.get(self.account_request_url)
        self.assertEqual(response.status_code, 200)
        handler_mock.assert_called_once_with(
            mock.ANY,
            link=None,
            redirect_url=self.account_request_url,
        )
