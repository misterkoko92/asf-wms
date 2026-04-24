from datetime import date, datetime
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptType,
    Warehouse,
)

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

    def test_scan_recipient_needs_prepare_selected_redirects_to_prefilled_shipment_create(self):
        fake_context = {
            "rows": [
                {
                    "selection_key": "10:20",
                    "can_prepare": True,
                    "destination_id": 12,
                    "prepare_shipper_contact_id": 34,
                    "prepare_recipient_contact_id": 56,
                    "prepare_product_code": "SKU-001",
                    "prepare_quantity": 7,
                }
            ],
            "destination_id": "12",
            "recipient_id": "42",
            "category_id": "9",
            "need_status": "to_serve",
            "priority": "high",
        }
        with mock.patch(
            "wms.views_scan_stock.build_scan_recipient_needs_context",
            return_value=fake_context,
        ):
            response = self.client.post(
                reverse("scan:scan_recipient_needs"),
                {
                    "action": "prepare_selected",
                    "selected_row_keys": ["10:20"],
                    "destination": "12",
                    "recipient": "42",
                    "category": "9",
                    "need_status": "to_serve",
                    "priority": "high",
                },
            )

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response["Location"])
        self.assertEqual(parsed.path, reverse("scan:scan_shipment_create"))
        query = parse_qs(parsed.query)
        self.assertEqual(query["destination"], ["12"])
        self.assertEqual(query["shipper_contact"], ["34"])
        self.assertEqual(query["recipient_contact"], ["56"])
        self.assertEqual(query["carton_count"], ["1"])
        self.assertEqual(query["line_1_product_code"], ["SKU-001"])
        self.assertEqual(query["line_1_quantity"], ["7"])

    def test_scan_recipient_needs_prepare_selected_rejects_mixed_groups(self):
        fake_context = {
            "rows": [
                {
                    "selection_key": "10:20",
                    "can_prepare": True,
                    "destination_id": 12,
                    "prepare_shipper_contact_id": 34,
                    "prepare_recipient_contact_id": 56,
                    "prepare_product_code": "SKU-001",
                    "prepare_quantity": 7,
                },
                {
                    "selection_key": "10:21",
                    "can_prepare": True,
                    "destination_id": 12,
                    "prepare_shipper_contact_id": 99,
                    "prepare_recipient_contact_id": 56,
                    "prepare_product_code": "SKU-002",
                    "prepare_quantity": 3,
                },
            ],
            "destination_id": "12",
            "recipient_id": "42",
            "category_id": "",
            "need_status": "to_serve",
            "priority": "",
        }
        with mock.patch(
            "wms.views_scan_stock.build_scan_recipient_needs_context",
            return_value=fake_context,
        ):
            response = self.client.post(
                reverse("scan:scan_recipient_needs"),
                {
                    "action": "prepare_selected",
                    "selected_row_keys": ["10:20", "10:21"],
                    "destination": "12",
                    "recipient": "42",
                    "category": "",
                    "need_status": "to_serve",
                    "priority": "",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f'{reverse("scan:scan_recipient_needs")}?destination=12&recipient=42&need_status=to_serve',
        )

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

    def test_scan_stock_update_get_renders_incomplete_products_context(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        product = Product.objects.create(
            name="Produit incomplet stock",
            is_incomplete=True,
            qr_code_image="qr_codes/stock-incomplete.png",
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-STOCK-INCOMPLETE",
            received_on=date(2026, 1, 2),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            location=self.location,
            source_receipt=receipt,
        )
        fake_form = object()

        with (
            mock.patch(
                "wms.views_scan_stock.ScanStockUpdateForm",
                return_value=fake_form,
            ),
            mock.patch(
                "wms.views_scan_stock.build_product_options",
                return_value=[{"id": 1}],
            ),
            mock.patch(
                "wms.views_scan_stock.build_location_data",
                return_value=[{"id": "A-01-001"}],
            ),
            mock.patch(
                "wms.views_scan_stock.render",
                side_effect=self._render_stub,
            ),
        ):
            response = self.client.get(
                reverse("scan:scan_stock_update"),
                {"incomplete_receipt_id": str(receipt.id)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/stock_update.html")
        self.assertEqual(response.context_data["active"], "stock_update")
        self.assertEqual(
            [item.id for item in response.context_data["incomplete_products"]],
            [product.id],
        )
        self.assertEqual(response.context_data["incomplete_products_receipt_id"], receipt.id)
        self.assertIn("incomplete_receipt_filter_form", response.context_data)

    def test_scan_stock_update_get_exposes_incomplete_product_suggestions(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        category = ProductCategory.objects.create(name="Thermomètres")
        for index in range(1, 4):
            Product.objects.create(
                sku=f"BRAUN-BASE-{index}",
                name=f"Produit Braun {index}",
                brand="BRAUN",
                category=category,
                default_location=self.location,
                tva=Decimal("0.055"),
                qr_code_image=f"qr_codes/braun-base-{index}.png",
            )
        incomplete_products = []
        for index in range(1, 4):
            product = Product.objects.create(
                name=f"BRAUN Thermometre {index}",
                is_incomplete=True,
                qr_code_image=f"qr_codes/braun-incomplete-{index}.png",
            )
            ProductLot.objects.create(
                product=product,
                lot_code=f"LOT-BRAUN-{index}",
                received_on=date(2026, 1, 2),
                status=ProductLotStatus.AVAILABLE,
                quantity_on_hand=1,
                location=self.location,
                source_receipt=receipt,
            )
            incomplete_products.append(product)

        response = self.client.get(
            reverse("scan:scan_stock_update"),
            {"incomplete_receipt_id": str(receipt.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                suggestion["field_name"]
                for suggestion in response.context["incomplete_product_suggestions"]
            ],
            ["brand", "category", "tva", "location"],
        )

    def test_scan_stock_update_apply_suggestion_updates_filtered_incomplete_products(self):
        receipt_1 = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        receipt_2 = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        category = ProductCategory.objects.create(name="Thermomètres")
        for index in range(1, 4):
            Product.objects.create(
                sku=f"BRAUN-BASE-APPLY-{index}",
                name=f"Produit Braun Apply {index}",
                brand="BRAUN",
                category=category,
                default_location=self.location,
                tva=Decimal("0.055"),
                qr_code_image=f"qr_codes/braun-base-apply-{index}.png",
            )
        targeted_products = []
        for index in range(1, 4):
            product = Product.objects.create(
                name=f"BRAUN Thermometre ciblé {index}",
                is_incomplete=True,
                qr_code_image=f"qr_codes/braun-target-{index}.png",
            )
            ProductLot.objects.create(
                product=product,
                lot_code=f"LOT-BRAUN-TARGET-{index}",
                received_on=date(2026, 1, 2),
                status=ProductLotStatus.AVAILABLE,
                quantity_on_hand=1,
                location=self.location,
                source_receipt=receipt_1,
            )
            targeted_products.append(product)
        untouched_product = Product.objects.create(
            name="BRAUN Thermometre hors filtre",
            is_incomplete=True,
            qr_code_image="qr_codes/braun-outside-filter.png",
        )
        ProductLot.objects.create(
            product=untouched_product,
            lot_code="LOT-BRAUN-OUTSIDE",
            received_on=date(2026, 1, 2),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            location=self.location,
            source_receipt=receipt_2,
        )

        response = self.client.post(
            reverse("scan:scan_stock_update"),
            {
                "action": "apply_incomplete_product_suggestion",
                "incomplete_receipt_id": str(receipt_1.id),
                "suggestion_id": "brand:BRAUN",
            },
        )

        self.assertEqual(response.status_code, 200)
        for product in targeted_products:
            product.refresh_from_db()
            self.assertEqual(product.brand, "BRAUN")
            self.assertNotEqual(
                product.name, f"BRAUN Thermometre ciblé {targeted_products.index(product) + 1}"
            )
        untouched_product.refresh_from_db()
        self.assertEqual(untouched_product.brand, "")

    def test_scan_stock_update_bulk_updates_filtered_incomplete_products(self):
        receipt_1 = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        receipt_2 = Receipt.objects.create(
            receipt_type=ReceiptType.PALLET,
            warehouse=self.location.warehouse,
        )
        product_1 = Product.objects.create(
            name="Mask 1",
            is_incomplete=True,
            qr_code_image="qr_codes/mask-stock-1.png",
        )
        product_2 = Product.objects.create(
            name="Mask 2",
            is_incomplete=True,
            qr_code_image="qr_codes/mask-stock-2.png",
        )
        ProductLot.objects.create(
            product=product_1,
            lot_code="LOT-STOCK-FILTER-1",
            received_on=date(2026, 1, 2),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            location=self.location,
            source_receipt=receipt_1,
        )
        ProductLot.objects.create(
            product=product_2,
            lot_code="LOT-STOCK-FILTER-2",
            received_on=date(2026, 1, 2),
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=1,
            location=self.location,
            source_receipt=receipt_2,
        )

        response = self.client.post(
            reverse("scan:scan_stock_update"),
            {
                "action": "bulk_update_incomplete_products",
                "incomplete_receipt_id": str(receipt_1.id),
                "selected_product_ids": [str(product_1.id)],
                "field_name": "brand",
                "field_value": "ASF",
            },
        )

        self.assertEqual(response.status_code, 200)
        product_1.refresh_from_db()
        product_2.refresh_from_db()
        self.assertEqual(product_1.brand, "ASF")
        self.assertEqual(product_2.brand, "")

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

    def test_scan_stock_includes_zero_stock_products_by_default(self):
        zero_stock_product = Product.objects.create(
            sku="STOCK-ZERO-001",
            name="Produit stock zero",
            default_location=self.location,
            qr_code_image="qr_codes/stock_zero.png",
        )

        response = self.client.get(reverse("scan:scan_stock"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["include_zero"])
        self.assertContains(response, zero_stock_product.name)

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
