from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from wms.carton_activity import find_last_carton_for_volunteer
from wms.models import (
    Carton,
    CartonFormat,
    CartonStatus,
    CartonVolunteerActivity,
    CartonVolunteerActivityAction,
    Location,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Product,
    ProductLot,
    VolunteerProfile,
    Warehouse,
)
from wms.preparateur_orders import get_preparateur_selected_order
from wms.preparateur_session import (
    build_preparateur_volunteer_label,
    clear_active_preparateur_volunteer,
    get_active_preparateur_volunteer,
    get_preparateur_greeting_name,
)
from wms.scan_permissions import is_scan_view_allowed_for_user
from wms.services import StockError

PREPARATEUR_HOME_PATH = "/scan/preparateur/"
PREPARATEUR_ORDER_SELECT_PATH = "/scan/preparateur/orders/"
ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY = "scan_active_preparateur_volunteer_id"
TEST_PASSWORD = "pass1234"  # pragma: allowlist secret


class _Session(dict):
    modified = False


class ScanPreparateurViewTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-preparateur-staff",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def _create_preparateur(self):
        user = get_user_model().objects.create_user(
            username="scan-preparateur-home",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        group, _ = Group.objects.get_or_create(name="Preparateur")
        user.groups.add(group)
        return user

    def _create_volunteer(self, *, first_name, last_name, username):
        user = get_user_model().objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
        )
        return VolunteerProfile.objects.create(user=user, is_active=True)

    def _ensure_location(self):
        if hasattr(self, "_location"):
            return self._location
        warehouse = Warehouse.objects.create(name="Entrepot preparateur")
        self._location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        return self._location

    def _create_stocked_product(self, *, sku, name, quantity_on_hand):
        location = self._ensure_location()
        product = Product.objects.create(
            sku=sku,
            name=name,
            brand="ACME",
            weight_g=100,
            length_cm=10,
            width_cm=10,
            height_cm=10,
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            quantity_on_hand=quantity_on_hand,
            location=location,
        )
        return product

    def _create_order(
        self,
        *,
        shipper_name,
        product,
        quantity,
        requested_delivery_date=None,
        created_at=None,
        review_status=OrderReviewStatus.APPROVED,
        status=OrderStatus.DRAFT,
    ):
        order = Order.objects.create(
            shipper_name=shipper_name,
            recipient_name="Association Test",
            destination_address="1 rue du test",
            destination_city="Paris",
            destination_country="France",
            review_status=review_status,
            status=status,
            requested_delivery_date=requested_delivery_date,
            created_by=self.staff_user,
        )
        order.lines.create(product=product, quantity=quantity)
        if created_at is not None:
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()
        return order

    def test_scan_root_redirects_preparateur_to_order_select(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        response = self.client.get(reverse("scan:scan_root"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], PREPARATEUR_ORDER_SELECT_PATH)

    def test_scan_preparateur_home_renders_disabled_actions_without_active_volunteer(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        response = self.client.get(PREPARATEUR_HOME_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir un bénévole")
        self.assertContains(response, "Préparer une commande")
        self.assertContains(response, "Préparer des colis non affectés")
        self.assertContains(response, "Voir dernier carton")
        self.assertContains(
            response,
            'class="btn btn-primary" disabled>Préparer une commande',
        )
        self.assertContains(
            response,
            'class="btn btn-secondary" disabled>Préparer des colis non affectés',
        )
        self.assertContains(
            response,
            'class="btn btn-tertiary" disabled>Voir dernier carton',
        )

    def test_scan_preparateur_home_renders_sorted_volunteer_selector_labels(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        self._create_volunteer(first_name="Claire", last_name="Zola", username="vol-zola")
        self._create_volunteer(first_name="Martin", last_name="Dupond", username="vol-dupond")

        response = self.client.get(PREPARATEUR_HOME_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="volunteer_id"')
        html = response.content.decode()
        self.assertIn("Martin DUPOND", html)
        self.assertIn("Claire ZOLA", html)
        self.assertLess(html.index("Martin DUPOND"), html.index("Claire ZOLA"))

    def test_scan_preparateur_home_post_sets_active_volunteer_and_greeting_persists(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-martin",
        )
        self.client.force_login(preparateur)

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "set_active_volunteer",
                "volunteer_id": volunteer.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], PREPARATEUR_HOME_PATH)
        session = self.client.session
        self.assertEqual(
            session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY],
            volunteer.id,
        )

        followup = self.client.get(reverse("scan:scan_pack"))

        self.assertEqual(followup.status_code, 200)
        self.assertContains(followup, "Bonjour Martin")
        self.assertContains(followup, reverse("scan:scan_preparateur_home"))

    def test_get_preparateur_selected_order_clears_session_for_non_approved_order(self):
        request = SimpleNamespace(session=_Session())
        product = self._create_stocked_product(
            sku="SKU-PREP-INVALID",
            name="Produit non approuve",
            quantity_on_hand=5,
        )
        order = self._create_order(
            shipper_name="Association en attente",
            product=product,
            quantity=1,
            review_status=OrderReviewStatus.PENDING,
        )
        request.session["preparateur_selected_order_id"] = order.id

        selected_order = get_preparateur_selected_order(request)

        self.assertIsNone(selected_order)
        self.assertNotIn("preparateur_selected_order_id", request.session)

    def test_is_scan_view_allowed_for_preparateur_requires_resolver_match(self):
        request = SimpleNamespace(user=self._create_preparateur())

        self.assertFalse(is_scan_view_allowed_for_user(request))

    def test_scan_preparateur_home_renders_grouped_recommended_orders(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-reco",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

        critical_product = self._create_stocked_product(
            sku="SKU-CRITICAL",
            name="Compresses",
            quantity_on_hand=20,
        )
        alpha_product = self._create_stocked_product(
            sku="SKU-ALPHA",
            name="Seringues",
            quantity_on_hand=20,
        )
        blocked_product = self._create_stocked_product(
            sku="SKU-BLOCKED",
            name="Gants",
            quantity_on_hand=0,
        )
        now = timezone.now()
        critical = self._create_order(
            shipper_name="Zulu Hope",
            product=critical_product,
            quantity=3,
            requested_delivery_date=date.today() + timedelta(days=1),
            created_at=now - timedelta(days=3),
        )
        second = self._create_order(
            shipper_name="Bravo Care",
            product=critical_product,
            quantity=2,
            requested_delivery_date=date.today() + timedelta(days=2),
            created_at=now - timedelta(days=2),
        )
        third = self._create_order(
            shipper_name="Echo Relief",
            product=critical_product,
            quantity=1,
            requested_delivery_date=date.today() + timedelta(days=3),
            created_at=now - timedelta(days=1),
        )
        alpha = self._create_order(
            shipper_name="Alpha Med",
            product=alpha_product,
            quantity=1,
            requested_delivery_date=date.today() + timedelta(days=4),
            created_at=now - timedelta(hours=12),
        )
        self._create_order(
            shipper_name="Omega Blocked",
            product=blocked_product,
            quantity=5,
            requested_delivery_date=date.today() + timedelta(days=1),
            created_at=now - timedelta(days=4),
        )

        response = self.client.get(PREPARATEUR_HOME_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les 3 commandes les plus critiques")
        self.assertContains(response, "Toutes les commandes")
        self.assertEqual(response.context["selected_order_id"], critical.id)
        order_groups = response.context["order_groups"]
        self.assertEqual(
            [group["label"] for group in order_groups],
            [
                "Les 3 commandes les plus critiques",
                "Toutes les commandes",
            ],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[0]["options"]],
            [critical.id, second.id, third.id],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[1]["options"]],
            [alpha.id, second.id, third.id, critical.id],
        )

    def test_scan_preparateur_home_rejects_unknown_volunteer_id(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "set_active_volunteer",
                "volunteer_id": "999999",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bénévole introuvable.")
        self.assertNotIn(
            ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY,
            self.client.session,
        )

    def test_scan_preparateur_home_requires_active_volunteer_for_actions(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "prepare_order",
                "order_id": "123",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez un bénévole avant de continuer.")

    def test_scan_preparateur_home_prepare_order_redirects_to_created_carton(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-order-action",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()
        order = self._create_order(
            shipper_name="Alpha Med",
            product=self._create_stocked_product(
                sku="SKU-HOME-ORDER",
                name="Compresses order",
                quantity_on_hand=20,
            ),
            quantity=2,
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.DRAFT,
        )
        created_carton = Carton.objects.create(
            code="CT-HOME-ORDER",
            status=CartonStatus.PACKED,
            prepared_by=volunteer.user,
        )

        def _prepare_side_effect(**kwargs):
            kwargs["created_cartons"].append(created_carton)
            return 0

        with mock.patch("wms.views_scan_preparateur.reserve_stock_for_order") as reserve_mock:
            with mock.patch(
                "wms.views_scan_preparateur.prepare_order",
                side_effect=_prepare_side_effect,
            ) as prepare_mock:
                response = self.client.post(
                    PREPARATEUR_HOME_PATH,
                    {
                        "action": "prepare_order",
                        "order_id": str(order.id),
                    },
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("scan:scan_carton_edit", args=[created_carton.id]),
        )
        reserve_mock.assert_called_once_with(order=order)
        prepare_mock.assert_called_once()
        self.assertEqual(
            prepare_mock.call_args.kwargs["prepared_by_user"],
            volunteer.user,
        )
        self.assertEqual(
            prepare_mock.call_args.kwargs["volunteer_profile"],
            volunteer,
        )
        self.assertEqual(prepare_mock.call_args.kwargs["actor_user"], preparateur)

    def test_scan_preparateur_home_prepare_order_rejects_unknown_order(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-order-missing",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "prepare_order",
                "order_id": "999999",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commande introuvable.")

    def test_scan_preparateur_home_prepare_order_handles_stock_error(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-order-stock-error",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()
        order = self._create_order(
            shipper_name="Stock Error Med",
            product=self._create_stocked_product(
                sku="SKU-STOCK-ERROR",
                name="Perfusion",
                quantity_on_hand=20,
            ),
            quantity=2,
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.DRAFT,
        )

        with mock.patch("wms.views_scan_preparateur.reserve_stock_for_order") as reserve_mock:
            with mock.patch(
                "wms.views_scan_preparateur.prepare_order",
                side_effect=StockError("stock bloqué"),
            ):
                response = self.client.post(
                    PREPARATEUR_HOME_PATH,
                    {
                        "action": "prepare_order",
                        "order_id": str(order.id),
                    },
                    follow=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stock bloqué")
        reserve_mock.assert_called_once_with(order=order)

    def test_scan_preparateur_home_prepare_order_without_carton_redirects_home(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-order-no-carton",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()
        order = self._create_order(
            shipper_name="No Carton Med",
            product=self._create_stocked_product(
                sku="SKU-NO-CARTON",
                name="Sparadrap",
                quantity_on_hand=20,
            ),
            quantity=2,
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )

        with mock.patch(
            "wms.views_scan_preparateur.attach_order_documents_to_shipment"
        ) as attach_mock:
            with mock.patch("wms.views_scan_preparateur.prepare_order") as prepare_mock:
                response = self.client.post(
                    PREPARATEUR_HOME_PATH,
                    {
                        "action": "prepare_order",
                        "order_id": str(order.id),
                    },
                    follow=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Préparation lancée.")
        attach_mock.assert_not_called()
        prepare_mock.assert_called_once()

    def test_scan_preparateur_home_view_last_carton_prefers_latest_non_shipped(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-last-carton",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()
        latest_non_shipped = Carton.objects.create(
            code="CT-LAST-PACKED",
            status=CartonStatus.PACKED,
            prepared_by=volunteer.user,
        )
        latest_shipped = Carton.objects.create(
            code="CT-LAST-SHIPPED",
            status=CartonStatus.SHIPPED,
            prepared_by=volunteer.user,
        )
        CartonVolunteerActivity.objects.create(
            carton=latest_non_shipped,
            volunteer=volunteer,
            action=CartonVolunteerActivityAction.PREPARED,
            actor=preparateur,
        )
        CartonVolunteerActivity.objects.create(
            carton=latest_shipped,
            volunteer=volunteer,
            action=CartonVolunteerActivityAction.EDITED,
            actor=preparateur,
        )

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "view_last_carton",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("scan:scan_carton_edit", args=[latest_non_shipped.id]),
        )

    def test_scan_preparateur_home_view_last_carton_shows_error_without_activity(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-last-carton-empty",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "view_last_carton",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucun carton trouvé pour ce bénévole.")

    def test_scan_preparateur_home_rejects_unknown_action(self):
        preparateur = self._create_preparateur()
        volunteer = self._create_volunteer(
            first_name="Martin",
            last_name="Dupond",
            username="vol-unknown-action",
        )
        self.client.force_login(preparateur)
        session = self.client.session
        session[ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

        response = self.client.post(
            PREPARATEUR_HOME_PATH,
            {
                "action": "not-supported",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Action préparateur inconnue.")

    def test_preparateur_whitelist_keeps_home_pack_runs_and_sync_only(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        dashboard_response = self.client.get(reverse("scan:scan_dashboard"))
        shipments_response = self.client.get(reverse("scan:scan_shipments_ready"))
        home_response = self.client.get(PREPARATEUR_HOME_PATH)
        pack_response = self.client.get(reverse("scan:scan_pack"))
        preparation_runs_response = self.client.get(reverse("scan:scan_preparation_run_list"))
        preparation_config_response = self.client.get(
            reverse("scan:scan_preparation_parameter_set_config")
        )
        sync_response = self.client.get(reverse("scan:scan_sync"))

        self.assertEqual(dashboard_response.status_code, 403)
        self.assertEqual(shipments_response.status_code, 403)
        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(pack_response.status_code, 200)
        self.assertEqual(preparation_runs_response.status_code, 200)
        self.assertEqual(preparation_config_response.status_code, 200)
        self.assertEqual(sync_response.status_code, 200)

    def test_preparateur_session_helpers_cover_fallbacks_and_missing_volunteer_cleanup(self):
        volunteer = self._create_volunteer(
            first_name="",
            last_name="",
            username="vol-fallback-username",
        )
        volunteer.short_name = "Momo"
        volunteer_last_name = self._create_volunteer(
            first_name="",
            last_name="Durand",
            username="vol-fallback-last-name",
        )

        request = mock.Mock()
        request.session = _Session(
            {
                ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY: volunteer.id + 999,
            }
        )
        active_volunteer = get_active_preparateur_volunteer(request)

        self.assertIsNone(active_volunteer)
        self.assertNotIn(
            ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY,
            request.session,
        )
        self.assertTrue(request.session.modified)
        self.assertEqual(build_preparateur_volunteer_label(volunteer), "vol-fallback-username")
        self.assertEqual(get_preparateur_greeting_name(volunteer), "Momo")
        self.assertEqual(get_preparateur_greeting_name(volunteer_last_name), "Durand")

        request.session = _Session(
            {
                ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY: volunteer.id,
            }
        )
        clear_active_preparateur_volunteer(request)
        self.assertNotIn(
            ACTIVE_PREPARATEUR_VOLUNTEER_SESSION_KEY,
            request.session,
        )
        self.assertTrue(request.session.modified)
        self.assertIsNone(find_last_carton_for_volunteer(None))
