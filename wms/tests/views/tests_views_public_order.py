from datetime import timedelta
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from wms.models import Order, Product, PublicOrderLink
from wms.services import StockError


class PublicOrderViewsTests(TestCase):
    def setUp(self):
        self.link = PublicOrderLink.objects.create(label="Public link")
        self.public_order_url = reverse("scan:scan_public_order", args=[self.link.token])

    def _create_order_for_link(self, link=None):
        link = link or self.link
        product = Product.objects.create(
            sku=f"PUB-{Product.objects.count() + 1}",
            name="Produit Public",
            qr_code_image="qr_codes/test.png",
        )
        order = Order.objects.create(
            public_link=link,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Beneficiaire",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order.lines.create(product=product, quantity=2)
        return order

    def test_scan_public_order_summary_404_for_missing_link(self):
        url = reverse("scan:scan_public_order_summary", args=[uuid4(), 1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_scan_public_order_summary_404_for_expired_link(self):
        expired = PublicOrderLink.objects.create(
            label="Expired",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        order = self._create_order_for_link(link=expired)
        url = reverse("scan:scan_public_order_summary", args=[expired.token, order.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_scan_public_order_summary_404_when_order_not_linked(self):
        other_link = PublicOrderLink.objects.create(label="Other link")
        order = self._create_order_for_link(link=other_link)
        url = reverse("scan:scan_public_order_summary", args=[self.link.token, order.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_scan_public_order_summary_renders_estimates(self):
        order = self._create_order_for_link()
        url = reverse("scan:scan_public_order_summary", args=[self.link.token, order.id])
        with mock.patch(
            "wms.views_public_order.get_default_carton_format",
            return_value=mock.sentinel.carton_format,
        ):
            with mock.patch(
                "wms.views_public_order.build_order_line_estimates",
                return_value=([{"product": "Produit Public"}], 3),
            ) as estimate_mock:
                response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_cartons"], 3)
        self.assertEqual(response.context["line_rows"], [{"product": "Produit Public"}])
        self.assertIs(response.context["carton_format"], mock.sentinel.carton_format)
        self.assertEqual(estimate_mock.call_args.kwargs["estimate_key"], "cartons_estimated")

    def test_scan_public_order_404_for_missing_link(self):
        response = self.client.get(reverse("scan:scan_public_order", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_scan_public_order_404_for_expired_link(self):
        expired = PublicOrderLink.objects.create(
            label="Expired",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.get(reverse("scan:scan_public_order", args=[expired.token]))
        self.assertEqual(response.status_code, 404)

    def test_scan_public_order_get_sets_summary_url_for_valid_order_query(self):
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[{"id": 1, "name": "Assoc"}],
            ):
                with mock.patch(
                    "wms.views_public_order.get_default_carton_format",
                    return_value=None,
                ):
                    with mock.patch(
                        "wms.views_public_order.build_carton_format_data",
                        return_value={},
                    ):
                        response = self.client.get(f"{self.public_order_url}?order=42")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["summary_url"],
            reverse("scan:scan_public_order_summary", args=[self.link.token, 42]),
        )

    def test_scan_public_order_get_ignorés_invalid_order_query(self):
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.get_default_carton_format",
                    return_value=None,
                ):
                    with mock.patch(
                        "wms.views_public_order.build_carton_format_data",
                        return_value={},
                    ):
                        response = self.client.get(f"{self.public_order_url}?order=abc")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["summary_url"])

    def test_scan_public_order_post_validates_required_fields_and_line_items(self):
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([], {}, {}),
                ):
                    with mock.patch(
                        "wms.views_public_order.create_public_order"
                    ) as create_mock:
                        with mock.patch(
                            "wms.views_public_order.get_default_carton_format",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_public_order.build_carton_format_data",
                                return_value={},
                            ):
                                response = self.client.post(self.public_order_url, {})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nom de l'association requis.", response.context["errors"])
        self.assertIn("Adresse requise.", response.context["errors"])
        self.assertIn("Ajoutez au moins un produit.", response.context["errors"])
        create_mock.assert_not_called()

    def test_scan_public_order_post_does_not_create_when_line_errors_exist(self):
        line_item = (SimpleNamespace(id=1), 2)
        payload = {
            "association_name": "Association Public",
            "association_line1": "1 Rue Test",
            "association_country": "France",
        }
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([line_item], {1: 2}, {"1": "invalid"}),
                ):
                    with mock.patch(
                        "wms.views_public_order.create_public_order"
                    ) as create_mock:
                        with mock.patch(
                            "wms.views_public_order.get_default_carton_format",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_public_order.build_carton_format_data",
                                return_value={},
                            ):
                                response = self.client.post(self.public_order_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["line_errors"], {"1": "invalid"})
        create_mock.assert_not_called()

    def test_scan_public_order_post_handles_stock_error(self):
        line_item = (SimpleNamespace(id=1), 2)
        payload = {
            "association_name": "Association Public",
            "association_line1": "1 Rue Test",
            "association_country": "France",
        }
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([line_item], {1: 2}, {}),
                ):
                    with mock.patch(
                        "wms.views_public_order.create_public_order",
                        side_effect=StockError("Stock insuffisant"),
                    ):
                        with mock.patch(
                            "wms.views_public_order.send_public_order_notifications"
                        ) as notify_mock:
                            with mock.patch(
                                "wms.views_public_order.get_default_carton_format",
                                return_value=None,
                            ):
                                with mock.patch(
                                    "wms.views_public_order.build_carton_format_data",
                                    return_value={},
                                ):
                                    response = self.client.post(self.public_order_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Stock insuffisant", response.context["errors"])
        notify_mock.assert_not_called()

    @override_settings(PUBLIC_ORDER_THROTTLE_SECONDS=300)
    def test_scan_public_order_post_rejects_throttled_submission(self):
        line_item = (SimpleNamespace(id=1), 2)
        payload = {
            "association_name": "Association Public",
            "association_email": "asso@example.com",
            "association_line1": "1 Rue Test",
            "association_country": "France",
        }
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([line_item], {1: 2}, {}),
                ):
                    with mock.patch(
                        "wms.views_public_order._reserve_throttle_slot",
                        return_value=False,
                    ):
                        with mock.patch(
                            "wms.views_public_order.create_public_order"
                        ) as create_mock:
                            response = self.client.post(self.public_order_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Une commande récente a déjà été envoyée. Merci de patienter quelques minutes.",
            response.context["errors"],
        )
        create_mock.assert_not_called()

    @override_settings(PUBLIC_ORDER_THROTTLE_SECONDS=300)
    def test_scan_public_order_post_releases_throttle_slot_on_stock_error(self):
        line_item = (SimpleNamespace(id=1), 2)
        payload = {
            "association_name": "Association Public",
            "association_email": "asso@example.com",
            "association_line1": "1 Rue Test",
            "association_country": "France",
        }
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([line_item], {1: 2}, {}),
                ):
                    with mock.patch(
                        "wms.views_public_order._reserve_throttle_slot",
                        return_value=True,
                    ) as reserve_mock:
                        with mock.patch(
                            "wms.views_public_order._release_throttle_slot",
                        ) as release_mock:
                            with mock.patch(
                                "wms.views_public_order.create_public_order",
                                side_effect=StockError("Stock insuffisant"),
                            ):
                                response = self.client.post(self.public_order_url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Stock insuffisant", response.context["errors"])
        reserve_mock.assert_called_once()
        release_mock.assert_called_once()

    def test_scan_public_order_post_success_redirects_with_order_summary(self):
        line_item = (SimpleNamespace(id=1), 2)
        fake_order = SimpleNamespace(id=77)
        fake_contact = SimpleNamespace(email="asso@example.com", phone="0102030405")
        payload = {
            "association_name": "Association Public",
            "association_email": "asso@example.com",
            "association_phone": "0102030405",
            "association_line1": "1 Rue Test",
            "association_line2": "Bat A",
            "association_postal_code": "75001",
            "association_city": "Paris",
            "association_country": "",
            "association_notes": "Besoin urgent",
            "association_contact_id": "",
        }
        with mock.patch(
            "wms.views_public_order.build_product_selection_data",
            return_value=([], {}, {}),
        ):
            with mock.patch(
                "wms.views_public_order.build_shipper_contact_payload",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_public_order.build_order_line_items",
                    return_value=([line_item], {1: 2}, {}),
                ):
                    with mock.patch(
                        "wms.views_public_order.create_public_order",
                        return_value=(fake_order, fake_contact),
                    ) as create_mock:
                        with mock.patch(
                            "wms.views_public_order.send_public_order_notifications"
                        ) as notify_mock:
                            response = self.client.post(self.public_order_url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{self.public_order_url}?order=77")
        create_form_data = create_mock.call_args.kwargs["form_data"]
        self.assertEqual(create_form_data["association_country"], "France")
        notify_mock.assert_called_once_with(
            mock.ANY,
            token=self.link.token,
            order=fake_order,
            form_data=create_form_data,
            contact=fake_contact,
        )
