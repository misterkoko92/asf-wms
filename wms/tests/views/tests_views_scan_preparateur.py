import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from wms.models import VolunteerProfile
from wms.preparateur_orders import PREPARATEUR_SELECTED_ORDER_SESSION_KEY

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
        session["preparateur_active_volunteer_id"] = volunteer.id
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
        self.assertEqual(session["preparateur_active_volunteer_id"], self.bravo_bob.id)

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
        self.assertEqual(session["preparateur_active_volunteer_id"], self.alpha_alice.id)

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
        self.assertEqual(session["preparateur_active_volunteer_id"], self.bravo_bob.id)
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
        self.assertEqual(session["preparateur_active_volunteer_id"], self.alpha_alice.id)
        self.assertNotIn(PREPARATEUR_SELECTED_ORDER_SESSION_KEY, session)
        self.assertNotIn("preparateur_order_plan", session)
