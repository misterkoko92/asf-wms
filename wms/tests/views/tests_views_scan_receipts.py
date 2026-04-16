from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Order,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderReviewStatus,
    Product,
    ProductCategory,
    Receipt,
    ReceiptType,
    Shipment,
    Warehouse,
)


class ScanReceiptsViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-receipts-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.warehouse = Warehouse.objects.create(name="Reception", code="REC")

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_receipt(self, receipt_type):
        return Receipt.objects.create(
            receipt_type=receipt_type,
            warehouse=self.warehouse,
        )

    def _create_inbound_order(self, *, review_status=OrderReviewStatus.PENDING):
        source_contact = Contact.objects.create(
            name="Association inbound receipt",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        order = Order.objects.create(
            association_contact=source_contact,
            shipper_name=source_contact.name,
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=review_status,
        )
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=2,
        )
        return order

    def test_scan_receipts_view_filters_pallet_receipts(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(f"{reverse('scan:scan_receipts_view')}?type=pallet")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receipts_view.html")
        self.assertEqual(response.context_data["filter_value"], "pallet")
        self.assertEqual(response.context_data["receipts"], [ReceiptType.PALLET])

    def test_scan_receipts_view_filters_association_receipts(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(f"{reverse('scan:scan_receipts_view')}?type=association")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter_value"], "association")
        self.assertEqual(response.context_data["receipts"], [ReceiptType.ASSOCIATION])

    def test_scan_receipts_view_defaults_to_all_for_unknown_filter(self):
        self._create_receipt(ReceiptType.PALLET)
        self._create_receipt(ReceiptType.ASSOCIATION)

        with mock.patch(
            "wms.views_scan_receipts.build_receipts_view_rows",
            side_effect=lambda qs: [item.receipt_type for item in qs],
        ):
            with mock.patch(
                "wms.views_scan_receipts.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(f"{reverse('scan:scan_receipts_view')}?type=unknown")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter_value"], "all")
        self.assertEqual(
            sorted(response.context_data["receipts"]),
            sorted([ReceiptType.PALLET, ReceiptType.ASSOCIATION]),
        )

    def test_scan_receipt_detail_renders_summary_lines_and_back_link(self):
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=self.warehouse,
        )

        response = self.client.get(reverse("scan:scan_receipt_detail", args=[receipt.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("scan:scan_receipts_view"))
        self.assertContains(response, receipt.reference)

    def test_scan_receipt_detail_exposes_legacy_edit_shortcuts(self):
        receipt = self._create_receipt(ReceiptType.ASSOCIATION)

        response = self.client.get(reverse("scan:scan_receipt_detail", args=[receipt.id]))

        self.assertContains(
            response,
            f"{reverse('scan:scan_receive_association')}?receipt_id={receipt.id}",
        )

    def test_scan_receive_get_renders_state_context(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": "RCP-1",
            "receipt_lines": [{"line": 1}],
            "pending_count": 2,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[{"id": 1}],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive.html")
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["selected_receipt"], "RCP-1")
        self.assertEqual(response.context_data["receipt_lines"], [{"line": 1}])
        self.assertEqual(response.context_data["pending_count"], 2)

    def test_scan_receive_post_returns_handler_response_when_available(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": None,
            "receipt_lines": [],
            "pending_count": 0,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_action",
                    return_value=(HttpResponse("handled"), None, None),
                ):
                    response = self.client.post(
                        reverse("scan:scan_receive"),
                        {"action": "receive_now"},
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")

    def test_scan_receive_post_updates_lines_and_pending_when_handler_returns_data(self):
        state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_receipt": None,
            "receipt_lines": [],
            "pending_count": 0,
        }
        with mock.patch(
            "wms.views_scan_receipts.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receipt_scan_state",
                return_value=state,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_action",
                    return_value=(None, [{"line": 99}], 4),
                ):
                    with mock.patch(
                        "wms.views_scan_receipts.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_receive"),
                            {"action": "receive_now"},
                        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive.html")
        self.assertEqual(response.context_data["receipt_lines"], [{"line": 99}])
        self.assertEqual(response.context_data["pending_count"], 4)

    def test_scan_receive_pallet_returns_state_response_when_present(self):
        with mock.patch(
            "wms.views_scan_receipts.build_receive_pallet_state",
            return_value={"response": HttpResponse("pallet-response")},
        ):
            response = self.client.post(
                reverse("scan:scan_receive_pallet"),
                {"action": "create"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pallet-response")

    def test_scan_receive_pallet_renders_context_when_no_state_response(self):
        state = {"response": None, "key": "value"}
        with mock.patch(
            "wms.views_scan_receipts.build_receive_pallet_state",
            return_value=state,
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receive_pallet_context",
                return_value={"context_key": "pallet"},
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive_pallet"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_pallet.html")
        self.assertEqual(response.context_data["context_key"], "pallet")

    def test_scan_receive_listing_returns_state_response_when_present(self):
        with mock.patch(
            "wms.views_scan_receipts.build_receive_listing_state",
            return_value={"response": HttpResponse("listing-response")},
        ):
            response = self.client.post(
                reverse("scan:scan_receive_listing"),
                {"action": "listing_upload"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "listing-response")

    def test_scan_receive_listing_renders_context_when_no_state_response(self):
        state = {"response": None, "key": "value"}
        with mock.patch(
            "wms.views_scan_receipts.build_receive_listing_state",
            return_value=state,
        ):
            with mock.patch(
                "wms.views_scan_receipts.build_receive_listing_context",
                return_value={"context_key": "listing"},
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive_listing"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_listing.html")
        self.assertEqual(response.context_data["context_key"], "listing")

    def test_scan_receive_listing_product_edit_updates_product_and_clears_incomplete(self):
        product = Product.objects.create(
            name="Mask",
            is_incomplete=True,
            qr_code_image="qr_codes/mask.png",
        )

        response = self.client.post(
            reverse("scan:scan_receive_listing_product_edit", args=[product.id]),
            {
                "action": "save",
                "name": "Mask",
                "brand": "ASF",
                "default_location": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_receive_listing"))
        product.refresh_from_db()
        self.assertEqual(product.brand, "ASF")
        self.assertFalse(product.is_incomplete)

    def test_scan_receive_listing_product_edit_get_renders_context(self):
        product = Product.objects.create(
            name="Mask",
            is_incomplete=True,
            qr_code_image="qr_codes/mask-edit.png",
        )

        with mock.patch(
            "wms.views_scan_receipts.render",
            side_effect=self._render_stub,
        ):
            response = self.client.get(
                reverse("scan:scan_receive_listing_product_edit", args=[product.id])
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_listing_product_edit.html")
        self.assertEqual(response.context_data["active"], "receive_listing")
        self.assertEqual(response.context_data["product"], product)

    def test_scan_receive_listing_bulk_sets_category_for_selected_products(self):
        product_1 = Product.objects.create(
            name="Mask 1",
            is_incomplete=True,
            qr_code_image="qr_codes/m1.png",
        )
        product_2 = Product.objects.create(
            name="Mask 2",
            is_incomplete=True,
            qr_code_image="qr_codes/m2.png",
        )
        category = ProductCategory.objects.create(name="medical")
        session = self.client.session
        session["pallet_listing_last_incomplete_product_ids"] = [product_1.id, product_2.id]
        session.save()

        response = self.client.post(
            reverse("scan:scan_receive_listing"),
            {
                "action": "bulk_update_incomplete_products",
                "selected_product_ids": [str(product_1.id), str(product_2.id)],
                "field_name": "category",
                "field_value": str(category.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        product_1.refresh_from_db()
        product_2.refresh_from_db()
        self.assertEqual(product_1.category_id, category.id)
        self.assertEqual(product_2.category_id, category.id)

    def test_scan_receive_listing_bulk_rejects_duplicate_ean_assignment(self):
        product_1 = Product.objects.create(
            name="Mask 1",
            is_incomplete=True,
            qr_code_image="qr_codes/m1b.png",
        )
        product_2 = Product.objects.create(
            name="Mask 2",
            is_incomplete=True,
            qr_code_image="qr_codes/m2b.png",
        )
        session = self.client.session
        session["pallet_listing_last_incomplete_product_ids"] = [product_1.id, product_2.id]
        session.save()

        response = self.client.post(
            reverse("scan:scan_receive_listing"),
            {
                "action": "bulk_update_incomplete_products",
                "selected_product_ids": [str(product_1.id), str(product_2.id)],
                "field_name": "ean",
                "field_value": "1234567890123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EAN")
        self.assertContains(response, "ne peut pas être appliqué en masse")

    def test_scan_receive_association_get_renders_context(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(2, [{"line": 1}, {"line": 2}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_receive_association"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_association.html")
        self.assertEqual(response.context_data["line_count"], 2)
        self.assertEqual(response.context_data["line_values"], [{"line": 1}, {"line": 2}])
        self.assertEqual(response.context_data["line_errors"], {})
        self.assertIs(response.context_data["create_form"], fake_form)

    def test_scan_receive_association_post_returns_handler_response(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(1, [{"line": 1}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_association_post",
                    return_value=(HttpResponse("association-response"), {}),
                ):
                    response = self.client.post(
                        reverse("scan:scan_receive_association"),
                        {"action": "create"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "association-response")

    def test_scan_receive_association_post_renders_with_line_errors(self):
        fake_form = object()
        with mock.patch(
            "wms.views_scan_receipts.build_hors_format_lines",
            return_value=(1, [{"line": 1}]),
        ):
            with mock.patch(
                "wms.views_scan_receipts.ScanReceiptAssociationForm",
                return_value=fake_form,
            ):
                with mock.patch(
                    "wms.views_scan_receipts.handle_receipt_association_post",
                    return_value=(None, {"0": "invalid"}),
                ):
                    with mock.patch(
                        "wms.views_scan_receipts.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_receive_association"),
                            {"action": "create"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/receive_association.html")
        self.assertEqual(response.context_data["line_errors"], {"0": "invalid"})

    def test_scan_receive_association_get_prefills_inbound_order_from_querystring(self):
        order = self._create_inbound_order()

        with mock.patch(
            "wms.views_scan_receipts.render",
            side_effect=self._render_stub,
        ):
            response = self.client.get(
                reverse("scan:scan_receive_association"),
                {"order_id": str(order.id)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context_data["create_form"].initial["inbound_delivery_order"],
            order.id,
        )
        self.assertEqual(
            response.context_data["create_form"].initial["source_contact"],
            order.association_contact_id,
        )

    def test_scan_receive_association_can_create_linked_shipment_from_selected_receipt(self):
        order = self._create_inbound_order(review_status=OrderReviewStatus.APPROVED)
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=self.warehouse,
            source_contact=order.association_contact,
        )
        order.inbound_delivery.receipt = receipt
        order.inbound_delivery.save(update_fields=["receipt"])
        shipment = Shipment.objects.create(
            reference="EXP-RECEIPT-LINK",
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )

        with (
            mock.patch(
                "wms.views_scan_receipts.create_shipment_for_order",
                return_value=shipment,
            ) as create_shipment_mock,
            mock.patch(
                "wms.views_scan_receipts.attach_order_documents_to_shipment"
            ) as attach_documents_mock,
        ):
            response = self.client.post(
                reverse("scan:scan_receive_association"),
                {
                    "action": "create_linked_shipment",
                    "receipt_id": str(receipt.id),
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id}),
        )
        create_shipment_mock.assert_called_once_with(order=order, force_new=True)
        attach_documents_mock.assert_called_once_with(order, shipment)
