from datetime import date, datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from wms.models import Location, Product, ProductLot, ProductLotStatus, Warehouse

EXPECTED_STOCK_PAGE_SIZE = 100


class ScanStockViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-stock-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        warehouse = Warehouse.objects.create(name="Stock Test", code="STK")
        self.location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku="STOCK-001",
            name="Produit Stock",
            default_location=self.location,
            qr_code_image="qr_codes/stock_test.png",
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-STOCK-001",
            received_on=date(2026, 1, 1),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=4,
            location=self.location,
        )

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def test_scan_stock_renders_context_from_helper(self):
        with mock.patch(
            "wms.views_scan_stock.build_stock_context",
            return_value={"active": "stock", "rows": [1]},
        ):
            with mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/stock.html")
        self.assertEqual(response.context_data, {"active": "stock", "rows": [1]})

    def test_scan_recipient_needs_renders_context_from_helper(self):
        fake_context = {
            "active": "recipient_needs",
            "rows": [
                {
                    "priority": "critical",
                    "recipient_admin_url": reverse(
                        "scan:scan_admin_recipient_organization_detail",
                        args=[99],
                    ),
                }
            ],
            "destination_id": str(self.location.warehouse.id),
            "recipient_id": "42",
        }
        with mock.patch(
            "wms.views_scan_stock.build_scan_recipient_needs_context",
            return_value=fake_context,
        ):
            with mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(
                    reverse("scan:scan_recipient_needs"),
                    {
                        "destination": "12",
                        "recipient": "42",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/recipient_needs_view.html")
        self.assertEqual(response.context_data, fake_context)

    def test_scan_stock_update_get_renders_context(self):
        fake_form = object()
        with (
            mock.patch(
                "wms.views_scan_stock.ScanStockUpdateForm",
                return_value=fake_form,
            ),
            mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[{"id": 1}],
            ) as build_product_options_mock,
            mock.patch(
                "wms.views_scan_stock.build_location_data",
                return_value=[{"id": "A-01-001"}],
            ),
            mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ),
        ):
            response = self.client.get(reverse("scan:scan_stock_update"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/stock_update.html")
        self.assertEqual(response.context_data["active"], "stock_update")
        self.assertIs(response.context_data["create_form"], fake_form)
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["location_data"], [{"id": "A-01-001"}])
        self.assertEqual(response.context_data["product_picker_mode"], "filter_select")
        build_product_options_mock.assert_called_once_with(compact=True)

    def test_scan_stock_update_large_product_list_uses_datalist_mode(self):
        fake_form = object()
        large_product_list = [{"id": index} for index in range(300)]
        with (
            mock.patch(
                "wms.views_scan_stock.ScanStockUpdateForm",
                return_value=fake_form,
            ),
            mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=large_product_list,
            ),
            mock.patch(
                "wms.views_scan_stock.build_location_data",
                return_value=[],
            ),
            mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ),
        ):
            response = self.client.get(reverse("scan:scan_stock_update"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["product_picker_mode"], "datalist")

    def test_scan_stock_update_post_returns_handler_response_when_available(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_stock.ScanStockUpdateForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_stock.build_location_data",
                    return_value=[],
                ):
                    with mock.patch(
                        "wms.views_scan_stock.handle_stock_update_post",
                        return_value=HttpResponse("updated"),
                    ):
                        response = self.client.post(
                            reverse("scan:scan_stock_update"),
                            {"action": "save"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "updated")

    def test_scan_out_get_renders_context(self):
        fake_form = object()
        with (
            mock.patch(
                "wms.views_scan_stock.ScanOutForm",
                return_value=fake_form,
            ),
            mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[{"id": 2}],
            ) as build_product_options_mock,
            mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ),
        ):
            response = self.client.get(reverse("scan:scan_out"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/out.html")
        self.assertIs(response.context_data["form"], fake_form)
        self.assertEqual(response.context_data["active"], "out")
        self.assertEqual(response.context_data["products_json"], [{"id": 2}])
        self.assertEqual(response.context_data["product_picker_mode"], "filter_select")
        build_product_options_mock.assert_called_once_with(compact=True)

    def test_scan_out_post_returns_handler_response_when_available(self):
        fake_form = object()
        with mock.patch("wms.views_scan_stock.ScanOutForm", return_value=fake_form):
            with mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_stock.handle_stock_out_post",
                    return_value=HttpResponse("out-post"),
                ):
                    response = self.client.post(reverse("scan:scan_out"), {"qty": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "out-post")

    def test_scan_sync_returns_json_state(self):
        fake_state = mock.Mock()
        fake_state.version = 12
        fake_state.last_changed_at = datetime(2026, 1, 5, 10, 30, 0)
        with mock.patch("wms.views_scan_stock.WmsChange.get_state", return_value=fake_state):
            response = self.client.get(reverse("scan:scan_sync"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["version"], 12)
        self.assertEqual(payload["changed_at"], "2026-01-05T10:30:00")

    def test_scan_stock_hides_category_and_warehouse_shortcuts(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Ajouter catégorie")
        self.assertNotContains(response, "Ajouter entrepôt")

    def test_scan_stock_hides_product_open_action_for_non_superuser(self):
        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<th>Actions</th>", html=True)
        self.assertNotContains(response, "Ouvrir")
        self.assertNotContains(response, 'data-table-tools="1"')

    def test_scan_stock_paginates_large_product_lists(self):
        for index in range(EXPECTED_STOCK_PAGE_SIZE + 5):
            product = Product.objects.create(
                sku=f"STOCK-PAGE-{index:03d}",
                name=f"Produit pagination {index:03d}",
                default_location=self.location,
            )
            ProductLot.objects.create(
                product=product,
                lot_code=f"LOT-PAGE-{index:03d}",
                received_on=date(2026, 1, 1),
                status=ProductLotStatus.AVAILABLE,
                quantity_on_hand=1,
                location=self.location,
            )

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["products_total_count"], EXPECTED_STOCK_PAGE_SIZE + 6)
        self.assertEqual(len(response.context["products"]), EXPECTED_STOCK_PAGE_SIZE)
        self.assertEqual(response.context["products_page"].number, 1)
        self.assertTrue(response.context["products_page"].has_next())
