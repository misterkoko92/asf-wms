import re
from datetime import date, timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    Location,
    Order,
    OrderReviewStatus,
    OrderStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    VolunteerProfile,
    Warehouse,
)
from wms.preparateur_home_queries import (
    ORDER_GROUP_ALL,
    ORDER_GROUP_CRITICAL,
    _build_order_option,
    _order_is_realisable_now,
    _remaining_total,
    _shipper_display_name,
    build_preparateur_order_groups,
)
from wms.preparateur_orders import PREPARATEUR_SELECTED_ORDER_SESSION_KEY
from wms.preparateur_session import (
    LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY,
    PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY,
    build_preparateur_volunteer_label,
    clear_active_preparateur_volunteer,
    get_active_preparateur_volunteer,
    get_preparateur_greeting_name,
    list_active_preparateur_volunteers,
)
from wms.scan_permissions import is_scan_view_allowed_for_user

TEST_PASSWORD = "pass1234"  # pragma: allowlist secret


class ScanPreparateurHomeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.preparateur = get_user_model().objects.create_user(
            username="scan-preparateur-home",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        Group.objects.get_or_create(name="Preparateur")[0].user_set.add(cls.preparateur)
        cls.alpha_alice = cls._create_volunteer(
            username="volunteer-alpha-alice",
            first_name="Alice",
            last_name="Alpha",
        )
        cls.alpha_zoe = cls._create_volunteer(
            username="volunteer-alpha-zoe",
            first_name="Zoe",
            last_name="Alpha",
        )
        cls.bravo_bob = cls._create_volunteer(
            username="volunteer-bravo-bob",
            first_name="Bob",
            last_name="Bravo",
        )
        cls._create_volunteer(
            username="volunteer-inactive",
            first_name="Inactive",
            last_name="Zulu",
            is_active=False,
        )

    @classmethod
    def _create_volunteer(cls, *, username, first_name, last_name, is_active=True):
        user = get_user_model().objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        return VolunteerProfile.objects.create(user=user, is_active=is_active)

    def setUp(self):
        self.client.force_login(self.preparateur)

    def _set_active_volunteer(self, volunteer):
        session = self.client.session
        session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY] = volunteer.id
        session.save()

    def test_scan_preparateur_home_lists_active_volunteers_sorted_and_disables_actions_without_selection(
        self,
    ):
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir un bénévole")
        self.assertFalse(response.context["has_active_volunteer"])
        self.assertIsNone(response.context["active_volunteer"])
        self.assertEqual(
            [row["id"] for row in response.context["volunteer_options"]],
            [self.alpha_alice.id, self.alpha_zoe.id, self.bravo_bob.id],
        )
        content = response.content.decode()
        self.assertRegex(
            content,
            re.compile(r'id="scan-preparateur-home-prepare-order"[^>]*disabled'),
        )
        self.assertRegex(
            content,
            re.compile(r'id="scan-preparateur-home-prepare-cartons"[^>]*disabled'),
        )
        self.assertNotContains(response, "Inactive ZULU")

    def test_scan_preparateur_home_post_stores_active_volunteer_in_session(self):
        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"volunteer_id": str(self.bravo_bob.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_home"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.bravo_bob.id)

    def test_scan_preparateur_home_prepare_order_redirects_to_order_select_with_active_volunteer(
        self,
    ):
        self._set_active_volunteer(self.alpha_alice)

        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_order"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_select"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.alpha_alice.id)

    def test_scan_preparateur_home_prepare_cartons_clears_selected_order_and_redirects_pack(self):
        self._set_active_volunteer(self.bravo_bob)
        session = self.client.session
        session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = 999
        session["preparateur_order_plan"] = {"order_id": 999, "cartons": []}
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_cartons"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.bravo_bob.id)
        self.assertNotIn(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, session)
        self.assertNotIn("preparateur_order_plan", session)

    def test_scan_preparateur_pack_start_clears_selected_order_and_plan_before_pack(self):
        self._set_active_volunteer(self.alpha_alice)
        session = self.client.session
        session[PREPARATEUR_SELECTED_ORDER_SESSION_KEY] = 123
        session["preparateur_order_plan"] = {"order_id": 123, "cartons": [{"index": 1}]}
        session.save()

        response = self.client.get(reverse("scan:scan_preparateur_pack_start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))
        session = self.client.session
        self.assertEqual(session[PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY], self.alpha_alice.id)
        self.assertNotIn(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, session)
        self.assertNotIn("preparateur_order_plan", session)

    def test_scan_preparateur_home_redirects_non_preparateur_to_dashboard(self):
        regular_staff = get_user_model().objects.create_user(
            username="scan-preparateur-regular-staff",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        self.client.force_login(regular_staff)
        response = self.client.get(reverse("scan:scan_preparateur_home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_dashboard"))

    def test_scan_preparateur_home_post_without_selection_clears_active_volunteer(self):
        self._set_active_volunteer(self.alpha_alice)

        response = self.client.post(reverse("scan:scan_preparateur_home"), {})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_home"))
        session = self.client.session
        self.assertNotIn(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, session)

    def test_scan_preparateur_home_actions_require_active_volunteer(self):
        response_order = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_order"},
        )
        response_cartons = self.client.post(
            reverse("scan:scan_preparateur_home"),
            {"action": "prepare_cartons"},
        )

        self.assertEqual(response_order.status_code, 302)
        self.assertEqual(response_order["Location"], reverse("scan:scan_preparateur_home"))
        self.assertEqual(response_cartons.status_code, 302)
        self.assertEqual(response_cartons["Location"], reverse("scan:scan_preparateur_home"))

    def test_scan_preparateur_pack_start_redirects_non_preparateur_to_pack(self):
        response = self.client.get(reverse("scan:scan_preparateur_pack_start"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_pack"))


class ScanPreparateurSessionHelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.alpha = cls._create_volunteer(
            username="volunteer-helper-alpha",
            first_name="Alice",
            last_name="Alpha",
        )
        cls.beta = cls._create_volunteer(
            username="volunteer-helper-beta",
            first_name="Bob",
            last_name="Beta",
        )
        cls.first_only = cls._create_volunteer(
            username="volunteer-helper-first",
            first_name="Claire",
            last_name="",
        )
        cls.last_only = cls._create_volunteer(
            username="volunteer-helper-last",
            first_name="",
            last_name="Durand",
        )
        cls.username_only = cls._create_volunteer(
            username="volunteer-helper-username",
            first_name="",
            last_name="",
        )

    @classmethod
    def _create_volunteer(cls, *, username, first_name, last_name):
        user = get_user_model().objects.create_user(
            username=username,
            password=TEST_PASSWORD,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        return VolunteerProfile.objects.create(user=user, is_active=True)

    def test_session_helpers_cover_cleanup_fallbacks_and_sorting(self):
        request = SimpleNamespace(
            session={
                PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.alpha.id + 999,
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )

        active_volunteer = get_active_preparateur_volunteer(request)

        self.assertIsNone(active_volunteer)
        self.assertNotIn(PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, request.session)
        self.assertNotIn(LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY, request.session)

        request = SimpleNamespace(
            session={
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )
        self.assertEqual(get_active_preparateur_volunteer(request), self.beta)

        request = SimpleNamespace(
            session={
                PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.alpha.id,
                LEGACY_PREPARATEUR_ACTIVE_VOLUNTEER_SESSION_KEY: self.beta.id,
            }
        )
        clear_active_preparateur_volunteer(request)
        self.assertEqual(request.session, {})

        self.assertEqual(
            [volunteer.id for volunteer in list_active_preparateur_volunteers()],
            [
                self.username_only.id,
                self.first_only.id,
                self.alpha.id,
                self.beta.id,
                self.last_only.id,
            ],
        )

    def test_preparateur_label_and_greeting_helpers_cover_all_fallbacks(self):
        no_user_volunteer = SimpleNamespace(user=None)

        self.assertEqual(build_preparateur_volunteer_label(no_user_volunteer), "")
        self.assertEqual(build_preparateur_volunteer_label(self.alpha), "Alice ALPHA")
        self.assertEqual(build_preparateur_volunteer_label(self.first_only), "Claire")
        self.assertEqual(build_preparateur_volunteer_label(self.last_only), "DURAND")
        self.assertEqual(
            build_preparateur_volunteer_label(self.username_only),
            self.username_only.user.username,
        )

        self.assertEqual(get_preparateur_greeting_name(no_user_volunteer), "")
        self.assertEqual(get_preparateur_greeting_name(self.alpha), "Alice")
        self.assertEqual(get_preparateur_greeting_name(self.last_only), "DURAND")
        self.assertEqual(
            get_preparateur_greeting_name(self.username_only),
            self.username_only.user.username,
        )

    def test_scan_permission_helper_requires_resolver_match_for_preparateur(self):
        preparateur = get_user_model().objects.create_user(
            username="scan-preparateur-permissions",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        Group.objects.get_or_create(name="Preparateur")[0].user_set.add(preparateur)
        request = SimpleNamespace(user=preparateur)

        self.assertFalse(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_cartons_ready")
        self.assertTrue(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_carton_document")
        self.assertTrue(is_scan_view_allowed_for_user(request))

        request.resolver_match = SimpleNamespace(url_name="scan_dashboard")
        self.assertFalse(is_scan_view_allowed_for_user(request))


class PreparateurHomeQueriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff_user = get_user_model().objects.create_user(
            username="scan-preparateur-queries",
            password=TEST_PASSWORD,
            is_staff=True,
        )
        cls.warehouse = Warehouse.objects.create(name="Preparateur WH", code="PWH")
        cls.location = Location.objects.create(
            warehouse=cls.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )

    def _create_stocked_product(self, *, sku, name, quantity_on_hand, quantity_reserved=0):
        product = Product.objects.create(
            sku=sku,
            name=name,
            weight_g=100,
            volume_cm3=100,
            default_location=self.location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            location=self.location,
        )
        return product

    def _create_order(
        self,
        *,
        shipper_name,
        product,
        quantity,
        reserved_quantity=0,
        prepared_quantity=0,
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
        order.lines.create(
            product=product,
            quantity=quantity,
            reserved_quantity=reserved_quantity,
            prepared_quantity=prepared_quantity,
        )
        if created_at is not None:
            Order.objects.filter(pk=order.pk).update(created_at=created_at)
            order.refresh_from_db()
        return order

    def test_preparateur_home_query_helpers_cover_display_option_and_remaining_quantity(self):
        order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="Shipper Name",
            reference="REF-001",
            id=10,
            requested_delivery_date=date(2026, 5, 1),
            lines=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(remaining_quantity=3),
                    SimpleNamespace(remaining_quantity=-2),
                ]
            ),
            created_at=date(2026, 4, 20),
        )
        reference_only_order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="",
            reference="REF-ONLY",
            id=11,
        )
        unnamed_order = SimpleNamespace(
            shipper_contact=None,
            shipper_name="",
            reference="",
            id=12,
        )

        self.assertEqual(_shipper_display_name(order), "Shipper Name")
        self.assertEqual(_shipper_display_name(reference_only_order), "REF-ONLY")
        self.assertEqual(_shipper_display_name(unnamed_order), "Commande 12")
        self.assertEqual(_remaining_total(order), 3)
        self.assertEqual(
            _build_order_option(order)["label"],
            "Shipper Name · REF-001 · reste 3 · livraison 01/05/2026",
        )

    def test_preparateur_home_query_helpers_cover_realisable_rules_and_grouping(self):
        full_product = self._create_stocked_product(
            sku="PREP-HQ-FULL",
            name="Produit Full",
            quantity_on_hand=8,
        )
        partial_product = self._create_stocked_product(
            sku="PREP-HQ-PARTIAL",
            name="Produit Partiel",
            quantity_on_hand=1,
        )
        reserved_product = self._create_stocked_product(
            sku="PREP-HQ-RESERVED",
            name="Produit Reserve",
            quantity_on_hand=0,
        )
        now = date(2026, 4, 20)

        critical = self._create_order(
            shipper_name="Zulu Hope",
            product=full_product,
            quantity=3,
            requested_delivery_date=now + timedelta(days=1),
        )
        alpha = self._create_order(
            shipper_name="Alpha Med",
            product=full_product,
            quantity=1,
            requested_delivery_date=now + timedelta(days=4),
        )
        self._create_order(
            shipper_name="Blocked",
            product=partial_product,
            quantity=5,
            requested_delivery_date=now + timedelta(days=2),
        )
        reserved = self._create_order(
            shipper_name="Reserved Flow",
            product=reserved_product,
            quantity=2,
            reserved_quantity=2,
            requested_delivery_date=now + timedelta(days=3),
            status=OrderStatus.RESERVED,
        )
        completed = self._create_order(
            shipper_name="Complete",
            product=full_product,
            quantity=2,
            prepared_quantity=2,
            requested_delivery_date=now + timedelta(days=5),
        )

        self.assertTrue(
            _order_is_realisable_now(
                critical,
                available_stock_by_product_id={full_product.id: 8},
            )
        )
        self.assertTrue(
            _order_is_realisable_now(
                reserved,
                available_stock_by_product_id={reserved_product.id: 0},
            )
        )
        self.assertFalse(
            _order_is_realisable_now(
                completed,
                available_stock_by_product_id={full_product.id: 8},
            )
        )
        self.assertFalse(
            _order_is_realisable_now(
                self._create_order(
                    shipper_name="Insufficient",
                    product=partial_product,
                    quantity=4,
                    requested_delivery_date=now + timedelta(days=6),
                ),
                available_stock_by_product_id={partial_product.id: 1},
            )
        )

        order_groups, selected_order_id = build_preparateur_order_groups()

        self.assertEqual(selected_order_id, critical.id)
        self.assertEqual(
            [group["label"] for group in order_groups],
            [ORDER_GROUP_CRITICAL, ORDER_GROUP_ALL],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[0]["options"]],
            [critical.id, reserved.id, alpha.id],
        )
        self.assertEqual(
            [option["order"].id for option in order_groups[1]["options"]],
            [alpha.id, reserved.id, critical.id],
        )
