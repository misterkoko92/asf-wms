from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonFormat,
    CartonSourceKind,
    CartonStatus,
    Location,
    Order,
    OrderInboundArrivalMode,
    OrderInboundDelivery,
    OrderLine,
    OrderReviewStatus,
    OrderShipmentLink,
    OrderStatus,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    Receipt,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    Warehouse,
)
from wms.order_view_helpers import build_orders_view_rows
from wms.preparateur_orders import (
    PREPARATEUR_ORDER_PLAN_SESSION_KEY,
    build_preparateur_order_picking_context,
    build_preparateur_selected_order_summary,
    get_preparateur_order_plan,
    get_preparateur_selected_order,
    mark_preparateur_plan_carton_ready,
)
from wms.services import StockError


class ScanOrdersViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-orders-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_order(
        self,
        *,
        association_name="",
        recipient_name="Recipient",
        review_status=OrderReviewStatus.PENDING,
        created_by=None,
    ):
        association_contact = None
        if association_name:
            association_contact = Contact.objects.create(
                name=association_name,
                contact_type=ContactType.ORGANIZATION,
                is_active=True,
            )
        return Order.objects.create(
            association_contact=association_contact,
            shipper_name="ASF",
            recipient_name=recipient_name,
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=review_status,
            created_by=created_by,
        )

    def _create_preparateur(self):
        user = get_user_model().objects.create_user(
            username="scan-orders-preparateur",
            password="pass1234",
            is_staff=True,
        )
        Group.objects.get_or_create(name="Preparateur")[0].user_set.add(user)
        return user

    def _create_stock_product(
        self,
        *,
        sku,
        name,
        quantity_on_hand,
        quantity_reserved=0,
        weight_g=250,
        volume_cm3=125,
        category=None,
    ):
        warehouse = Warehouse.objects.create(name=f"WH-{sku}", code=sku[:4].upper())
        location = Location.objects.create(
            warehouse=warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        product = Product.objects.create(
            sku=sku,
            name=name,
            category=category,
            default_location=location,
            weight_g=weight_g,
            volume_cm3=volume_cm3,
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            location=location,
        )
        return product

    def _create_order_line(
        self,
        *,
        order,
        product,
        quantity,
        reserved_quantity=0,
        prepared_quantity=0,
    ):
        return OrderLine.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            reserved_quantity=reserved_quantity,
            prepared_quantity=prepared_quantity,
        )

    def test_scan_order_get_renders_context(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": "ORD-1",
            "order_lines": [{"line": 1}],
            "remaining_total": 3,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[{"id": 1}],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(reverse("scan:scan_order"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/order.html")
        self.assertEqual(response.context_data["active"], "order")
        self.assertEqual(response.context_data["products_json"], [{"id": 1}])
        self.assertEqual(response.context_data["selected_order"], "ORD-1")
        self.assertEqual(response.context_data["order_lines"], [{"line": 1}])
        self.assertEqual(response.context_data["remaining_total"], 3)

    def test_scan_order_post_returns_handler_response_when_available(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": None,
            "order_lines": [],
            "remaining_total": 0,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.handle_order_action",
                    return_value=(HttpResponse("handled"), None, None),
                ):
                    response = self.client.post(
                        reverse("scan:scan_order"),
                        {"action": "receive_now"},
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")

    def test_scan_order_post_updates_lines_and_remaining(self):
        order_state = {
            "select_form": object(),
            "create_form": object(),
            "line_form": object(),
            "selected_order": None,
            "order_lines": [],
            "remaining_total": 0,
        }
        with mock.patch(
            "wms.views_scan_orders.build_product_options",
            return_value=[],
        ):
            with mock.patch(
                "wms.views_scan_orders.build_order_scan_state",
                return_value=order_state,
            ):
                with mock.patch(
                    "wms.views_scan_orders.handle_order_action",
                    return_value=(None, [{"line": 5}], 8),
                ):
                    with mock.patch(
                        "wms.views_scan_orders.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.post(
                            reverse("scan:scan_order"),
                            {"action": "receive_now"},
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/order.html")
        self.assertEqual(response.context_data["order_lines"], [{"line": 5}])
        self.assertEqual(response.context_data["remaining_total"], 8)

    def test_scan_orders_view_get_renders_rows_context(self):
        self._create_order(
            association_name="Association Pending",
            review_status=OrderReviewStatus.PENDING,
        )
        self._create_order(
            association_name="Association Changes",
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
        )
        self._create_order(
            association_name="Association Approved",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order(
            association_name="Association Rejected",
            review_status=OrderReviewStatus.REJECTED,
        )

        response = self.client.get(reverse("scan:scan_orders_view"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active"], "orders_view")
        self.assertEqual(response.context["total_count"], 4)
        self.assertEqual(response.context["orders_page"].number, 1)
        self.assertEqual(len(response.context["orders"]), 4)
        self.assertEqual(
            [card["id"] for card in response.context["summary_cards"]],
            [
                "to-validate",
                "changes-requested",
                "approved-without-shipment",
                "rejected-orders",
            ],
        )
        self.assertEqual(
            [card["value"] for card in response.context["summary_cards"]],
            [1, 1, 1, 1],
        )
        self.assertEqual(response.context["approved_status"], OrderReviewStatus.APPROVED)
        self.assertEqual(response.context["rejected_status"], OrderReviewStatus.REJECTED)
        self.assertEqual(
            response.context["changes_status"],
            OrderReviewStatus.CHANGES_REQUESTED,
        )

    def test_scan_orders_view_post_returns_handler_response_when_available(self):
        with mock.patch(
            "wms.views_scan_orders.handle_orders_view_action",
            return_value=HttpResponse("orders-handled"),
        ):
            response = self.client.post(
                reverse("scan:scan_orders_view"),
                {"action": "approve"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "orders-handled")

    def test_scan_orders_view_post_renders_when_handler_returns_none(self):
        self._create_order(association_name="Association visible")

        with mock.patch(
            "wms.views_scan_orders.handle_orders_view_action",
            return_value=None,
        ):
            response = self.client.post(
                reverse("scan:scan_orders_view"),
                {"action": "noop"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["orders"]), 1)
        self.assertEqual(response.context["orders"][0]["association_name"], "Association visible")

    def test_scan_orders_view_searches_all_rows_then_resets_to_page_one(self):
        for index in range(105):
            self._create_order(association_name=f"Association orders {index:03d}")
        self._create_order(association_name="Association compresse orders")

        response = self.client.get(reverse("scan:scan_orders_view"), {"q": "compresse"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Association compresse orders")
        self.assertEqual(response.context["orders_page"].number, 1)
        self.assertEqual(len(response.context["orders"]), 1)

    def test_scan_orders_view_paginates_after_one_hundred_rows(self):
        for index in range(105):
            self._create_order(association_name=f"Association pagination {index:03d}")

        response = self.client.get(reverse("scan:scan_orders_view"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["orders"]), 100)
        self.assertTrue(response.context["orders_page"].has_next())

    def test_scan_orders_view_supports_contact_sort(self):
        self._create_order(association_name="Zulu Orders")
        self._create_order(association_name="Alpha Orders")

        response = self.client.get(reverse("scan:scan_orders_view"), {"sort": "contact_desc"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["association_name"] for row in response.context["orders"]],
            ["Zulu Orders", "Alpha Orders"],
        )

    def test_scan_orders_view_uses_open_links_instead_of_inline_review_form(self):
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Action",
            destination_address="3 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.CHANGES_REQUESTED,
        )

        response = self.client.get(reverse("scan:scan_orders_view"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("scan:scan_order_detail", args=[order.id]))
        self.assertContains(response, ">Ouvrir<", html=False)
        self.assertNotContains(response, 'name="review_status"')

    def test_scan_order_detail_get_renders_context(self):
        shipper_contact = Contact.objects.create(
            name="Expediteur Detail",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name="Destinataire Detail",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Detail",
            destination_address="4 rue de la Paix",
            destination_city="Paris",
            destination_country="France",
            shipper_contact=shipper_contact,
            recipient_contact=recipient_contact,
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )

        response = self.client.get(reverse("scan:scan_order_detail", args=[order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contacts & Destination")
        self.assertContains(response, "Expediteur Detail")
        self.assertContains(response, "Destinataire Detail")
        self.assertContains(response, "4 rue de la Paix")
        self.assertContains(response, "Revue de commande")
        self.assertContains(response, "Actions métier")
        self.assertContains(response, "Créer les colis et l&#x27;expédition")
        self.assertContains(response, "Lignes de commande")

    def test_scan_order_detail_get_renders_multi_shipment_confirmation(self):
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Detail",
            destination_address="4 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )

        with mock.patch(
            "wms.order_view_helpers.estimate_order_preparation_carton_count",
            return_value=(32, ["Produit test: poids/volume manquants."]),
        ):
            response = self.client.get(
                reverse("scan:scan_order_detail", args=[order.id]),
                {"prepare_confirm": "1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La commande va générer 32 colis")
        self.assertContains(response, 'name="shipment_count"')
        self.assertContains(response, 'value="4"')
        self.assertContains(response, 'name="cartons_per_shipment"', count=4)
        self.assertContains(response, 'value="10"', count=3)
        self.assertContains(response, 'value="2"')
        self.assertContains(response, "Produit test: poids/volume manquants.")

    def test_scan_order_detail_redirects_when_prepare_confirmation_fails(self):
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Detail",
            destination_address="4 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )

        with mock.patch(
            "wms.views_scan_orders.build_order_detail_payload",
            side_effect=StockError("Stock insuffisant."),
        ):
            response = self.client.get(
                reverse("scan:scan_order_detail", args=[order.id]),
                {"prepare_confirm": "1"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_order_detail", args=[order.id]))

    def test_scan_shipment_dossier_exposes_create_all_cartons_for_linked_order(self):
        product = Product.objects.create(sku="SHIP-ORDER-1", name="Produit commande")
        shipment = Shipment.objects.create(
            reference="EXP-ORDER-HEADER",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
            shipment=shipment,
        )
        OrderLine.objects.create(order=order, product=product, quantity=2, reserved_quantity=2)
        OrderShipmentLink.objects.create(order=order, shipment=shipment, created_by=self.staff_user)

        response = self.client.get(reverse("scan:scan_shipment_edit", args=[shipment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Créer tous les colis")
        self.assertContains(response, reverse("scan:scan_order_detail", args=[order.id]))

    def test_scan_order_detail_returns_404_for_unknown_order(self):
        response = self.client.get(reverse("scan:scan_order_detail", args=[999999]))

        self.assertEqual(response.status_code, 404)

    def test_scan_order_detail_post_returns_handler_response_when_available(self):
        order = Order.objects.create(
            shipper_name="ASF",
            recipient_name="Association Detail",
            destination_address="4 rue de la Paix",
            destination_country="France",
            review_status=OrderReviewStatus.PENDING,
        )

        with mock.patch(
            "wms.views_scan_orders.handle_order_detail_action",
            return_value=HttpResponse("detail-handled"),
        ):
            response = self.client.post(
                reverse("scan:scan_order_detail", args=[order.id]),
                {"action": "update_status", "review_status": OrderReviewStatus.APPROVED},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "detail-handled")

    def test_build_orders_view_rows_allows_creating_additional_shipments_for_approved_order(self):
        shipment = Shipment.objects.create(
            reference="EXP-ORDERS-001",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=None,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            shipment=shipment,
        )

        rows = build_orders_view_rows(Order.objects.filter(id=order.id))

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["can_create_shipment"])

    def test_build_orders_view_rows_exposes_inbound_receipt_shortcut_and_linked_shipments(self):
        warehouse = Warehouse.objects.create(name="Scan Orders", code="SO")
        source_contact = Contact.objects.create(
            name="Association inbound",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        receipt = Receipt.objects.create(
            receipt_type=ReceiptType.ASSOCIATION,
            warehouse=warehouse,
            source_contact=source_contact,
        )
        shipment = Shipment.objects.create(
            reference="EXP-ORDERS-INBOUND",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=source_contact,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
        )
        OrderInboundDelivery.objects.create(
            order=order,
            arrival_mode=OrderInboundArrivalMode.DROPOFF_WAREHOUSE,
            declared_carton_count=3,
            receipt=receipt,
        )
        Carton.objects.create(
            code="AS-ORDERS-001",
            status=CartonStatus.PACKED,
            source_kind=CartonSourceKind.SHIPPER_RECEIVED,
            source_receipt=receipt,
        )
        OrderShipmentLink.objects.create(order=order, shipment=shipment, created_by=self.staff_user)

        rows = build_orders_view_rows(Order.objects.filter(id=order.id))

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["receipt_shortcut_url"],
            f"{reverse('scan:scan_receive_association')}?order_id={order.id}",
        )
        self.assertEqual(rows[0]["shipper_received_unassigned_carton_count"], 1)
        self.assertEqual(rows[0]["linked_shipments"][0]["reference"], shipment.reference)

    def test_scan_orders_view_create_shipment_reuses_existing_approved_order_shipment(self):
        existing_shipment = Shipment.objects.create(
            reference="EXP-ORDERS-EXISTING",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = Order.objects.create(
            association_contact=None,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
            review_status=OrderReviewStatus.APPROVED,
            shipment=existing_shipment,
        )

        with (
            mock.patch(
                "wms.order_view_handlers.create_shipment_for_order",
                return_value=existing_shipment,
            ) as create_shipment_mock,
            mock.patch("wms.order_view_handlers.attach_order_documents_to_shipment") as attach_mock,
        ):
            response = self.client.post(
                reverse("scan:scan_orders_view"),
                {
                    "action": "create_shipment",
                    "order_id": str(order.id),
                },
            )

        self.assertEqual(response.status_code, 302)
        create_shipment_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, existing_shipment)
        self.assertEqual(
            response.url, reverse("scan:scan_shipment_edit", args=[existing_shipment.id])
        )

    def test_scan_preparateur_order_select_lists_only_approved_orders(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        selectable_product = self._create_stock_product(
            sku="PREP-LIST",
            name="Produit Sélectionnable",
            quantity_on_hand=10,
        )
        pending = self._create_order(
            association_name="Association En Attente",
            review_status=OrderReviewStatus.PENDING,
        )
        self._create_order_line(order=pending, product=selectable_product, quantity=2)
        approved = self._create_order(
            association_name="Association Validée",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=approved, product=selectable_product, quantity=3)

        response = self.client.get(reverse("scan:scan_preparateur_order_select"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir une commande")
        self.assertContains(response, approved.reference or f"CMD-{approved.id}")
        self.assertContains(response, "Association Validée")
        self.assertNotContains(response, "Association En Attente")

    def test_scan_preparateur_order_select_groups_orders_by_feasibility(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        full_product = self._create_stock_product(
            sku="PREP-FULL",
            name="Produit Full",
            quantity_on_hand=8,
            quantity_reserved=0,
        )
        partial_product = self._create_stock_product(
            sku="PREP-PART",
            name="Produit Partiel",
            quantity_on_hand=2,
            quantity_reserved=1,
        )
        unavailable_product = self._create_stock_product(
            sku="PREP-NO",
            name="Produit Rupture",
            quantity_on_hand=3,
            quantity_reserved=3,
        )

        older_full = self._create_order(
            association_name="Association Full Ancienne",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=older_full, product=full_product, quantity=4)

        newer_full = self._create_order(
            association_name="Association Full Recente",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=newer_full, product=full_product, quantity=3)

        partial_order = self._create_order(
            association_name="Association Partielle",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(
            order=partial_order,
            product=partial_product,
            quantity=5,
            reserved_quantity=1,
        )

        unavailable_order = self._create_order(
            association_name="Association Rupture",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=unavailable_order, product=unavailable_product, quantity=4)

        no_lines_order = self._create_order(
            association_name="Association Sans Lignes",
            review_status=OrderReviewStatus.APPROVED,
        )
        prepared_order = self._create_order(
            association_name="Association Déjà Préparée",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(
            order=prepared_order,
            product=full_product,
            quantity=2,
            prepared_quantity=2,
        )
        pending_order = self._create_order(
            association_name="Association Pending Préparateur",
            review_status=OrderReviewStatus.PENDING,
        )
        self._create_order_line(order=pending_order, product=full_product, quantity=2)

        response = self.client.get(reverse("scan:scan_preparateur_order_select"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Réalisables à 100%")
        self.assertContains(response, "Réalisables partiellement")
        self.assertContains(response, "Non réalisables pour le moment")
        self.assertEqual(
            [row["order"].id for row in response.context["order_groups"]["100_percent"]],
            [newer_full.id, older_full.id],
        )
        self.assertEqual(
            [row["order"].id for row in response.context["order_groups"]["partial"]],
            [partial_order.id],
        )
        self.assertEqual(
            [row["order"].id for row in response.context["order_groups"]["unavailable"]],
            [unavailable_order.id],
        )
        self.assertNotContains(response, no_lines_order.association_contact.name)
        self.assertNotContains(response, prepared_order.association_contact.name)
        self.assertNotContains(response, pending_order.association_contact.name)

    def test_scan_preparateur_order_select_stores_selection_and_redirects_to_prepare_page(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        shipment = Shipment.objects.create(
            reference="EXP-PREP-001",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        order = self._create_order(
            association_name="Association Préparateur",
            review_status=OrderReviewStatus.APPROVED,
        )
        order.shipment = shipment
        order.save(update_fields=["shipment"])

        response = self.client.post(
            reverse("scan:scan_preparateur_order_select"),
            {"order_id": str(order.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_prepare"))
        session = self.client.session
        self.assertEqual(session["preparateur_selected_order_id"], order.id)

    def test_scan_preparateur_order_select_redirects_non_preparateur_to_orders_view(self):
        response = self.client.get(reverse("scan:scan_preparateur_order_select"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_orders_view"))

    def test_scan_preparateur_order_prepare_renders_generated_cartons_and_picking_actions(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-PLAN",
            name="Produit Plan",
            quantity_on_hand=10,
            weight_g=100,
            volume_cm3=100,
        )
        order = self._create_order(
            association_name="Association Plan",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=3)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        response = self.client.get(reverse("scan:scan_preparateur_order_prepare"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Liste des colis à préparer")
        self.assertContains(response, "Télécharger le picking")
        self.assertContains(response, "Colis 1")
        self.assertContains(response, "Produit Plan")
        self.assertContains(response, "Marquer prêt")

    def test_scan_preparateur_order_prepare_uses_standard_format_by_family(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        CartonFormat.objects.create(
            name="Fallback Default",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        mm_format = CartonFormat.objects.create(
            name="MM Standard",
            length_cm=12,
            width_cm=10,
            height_cm=8,
            max_weight_g=5000,
        )
        cn_format = CartonFormat.objects.create(
            name="CN Standard",
            length_cm=20,
            width_cm=15,
            height_cm=10,
            max_weight_g=7000,
        )
        category_mm = ProductCategory.objects.create(name="MM")
        category_cn = ProductCategory.objects.create(name="CN")
        product_mm = self._create_stock_product(
            sku="PREP-FMT-MM",
            name="Produit Format MM",
            quantity_on_hand=4,
            category=category_mm,
        )
        product_cn = self._create_stock_product(
            sku="PREP-FMT-CN",
            name="Produit Format CN",
            quantity_on_hand=4,
            category=category_cn,
        )
        order = self._create_order(
            association_name="Association Formats",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product_mm, quantity=1)
        self._create_order_line(order=order, product=product_cn, quantity=1)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        response = self.client.get(reverse("scan:scan_preparateur_order_prepare"))

        self.assertEqual(response.status_code, 200)
        cartons_by_family = {
            carton["family"]: carton for carton in response.context["plan"]["cartons"]
        }
        self.assertEqual(cartons_by_family["MM"]["carton_format_label"], mm_format.name)
        self.assertEqual(cartons_by_family["MM"]["carton_size"]["length_cm"], 12.0)
        self.assertEqual(cartons_by_family["CN"]["carton_format_label"], cn_format.name)
        self.assertEqual(cartons_by_family["CN"]["carton_size"]["length_cm"], 20.0)

    def test_scan_preparateur_order_prepare_forced_carton_count_stores_plan_and_warns(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        CartonFormat.objects.create(
            name="Fallback Default Forced",
            length_cm=5,
            width_cm=10,
            height_cm=1,
            max_weight_g=1000,
            is_default=True,
        )
        category_mm = ProductCategory.objects.create(name="MM")
        product = self._create_stock_product(
            sku="PREP-FORCE",
            name="Produit Force",
            quantity_on_hand=53,
            weight_g=1,
            volume_cm3=1,
            category=category_mm,
        )
        order = self._create_order(
            association_name="Association Force",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=53)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        auto_response = self.client.get(reverse("scan:scan_preparateur_order_prepare"))
        self.assertEqual(auto_response.status_code, 200)
        self.assertEqual(len(auto_response.context["plan"]["cartons"]), 2)

        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "update_carton_count",
                "forced_carton_count": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_prepare"))
        forced_plan = self.client.session[PREPARATEUR_ORDER_PLAN_SESSION_KEY]
        self.assertEqual(forced_plan["forced_carton_count"], 1)
        self.assertEqual(len(forced_plan["cartons"]), 1)
        self.assertEqual(forced_plan["cartons"][0]["items"][0]["quantity"], 53)
        self.assertTrue(any("forcé" in warning for warning in forced_plan["warnings"]))
        self.assertTrue(any("dépasse" in warning for warning in forced_plan["warnings"]))
        self.assertEqual(Carton.objects.count(), 0)
        self.assertEqual(ProductLot.objects.get(product=product).quantity_on_hand, 53)

    def test_scan_preparateur_order_prepare_rejects_invalid_forced_carton_count(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-FORCE-INVALID",
            name="Produit Force Invalid",
            quantity_on_hand=3,
        )
        order = self._create_order(
            association_name="Association Force Invalid",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=1)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "update_carton_count",
                "forced_carton_count": "0",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nombre de colis invalide.")

    def test_scan_preparateur_order_prepare_restores_auto_carton_count_when_blank(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        CartonFormat.objects.create(
            name="Fallback Default Auto",
            length_cm=5,
            width_cm=10,
            height_cm=1,
            max_weight_g=1000,
            is_default=True,
        )
        category_mm = ProductCategory.objects.create(name="MM")
        product = self._create_stock_product(
            sku="PREP-FORCE-AUTO",
            name="Produit Force Auto",
            quantity_on_hand=53,
            weight_g=1,
            volume_cm3=1,
            category=category_mm,
        )
        order = self._create_order(
            association_name="Association Force Auto",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=53)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        forced_response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "update_carton_count",
                "forced_carton_count": "1",
            },
        )
        self.assertEqual(forced_response.status_code, 302)

        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "update_carton_count",
                "forced_carton_count": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calcul automatique des colis restauré.")
        plan = self.client.session[PREPARATEUR_ORDER_PLAN_SESSION_KEY]
        self.assertIsNone(plan["forced_carton_count"])
        self.assertEqual(len(plan["cartons"]), 2)

    def test_scan_preparateur_order_prepare_marks_plan_carton_ready_and_updates_order(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-READY",
            name="Produit Pret",
            quantity_on_hand=10,
            weight_g=100,
            volume_cm3=100,
        )
        order = self._create_order(
            association_name="Association Prête",
            review_status=OrderReviewStatus.APPROVED,
        )
        line = self._create_order_line(order=order, product=product, quantity=2)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        warmup = self.client.get(reverse("scan:scan_preparateur_order_prepare"))
        self.assertEqual(warmup.status_code, 200)

        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "mark_carton_ready",
                "carton_index": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_prepare"))

        order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(line.prepared_quantity, 2)
        self.assertEqual(order.status, OrderStatus.READY)
        self.assertIsNotNone(order.shipment_id)

        carton = Carton.objects.get(shipment=order.shipment)
        self.assertEqual(carton.status, CartonStatus.PACKED)

        follow_up = self.client.get(reverse("scan:scan_preparateur_order_prepare"))
        self.assertEqual(follow_up.status_code, 200)
        self.assertContains(follow_up, carton.code)
        self.assertContains(follow_up, reverse("scan:scan_carton_edit", args=[carton.id]))

    def test_scan_preparateur_order_prepare_marks_existing_order_shipment_ready(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-SHIP",
            name="Produit Shipment",
            quantity_on_hand=10,
            weight_g=100,
            volume_cm3=100,
        )
        order = self._create_order(
            association_name="Association Shipment",
            review_status=OrderReviewStatus.APPROVED,
        )
        target_shipment = Shipment.objects.create(
            reference="EXP-PREP-TARGET",
            status=ShipmentStatus.DRAFT,
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="1 Rue Test",
            destination_country="France",
        )
        other_shipment = Shipment.objects.create(
            reference="EXP-PREP-OTHER",
            status=ShipmentStatus.DRAFT,
            shipper_name="Other",
            recipient_name="Other",
            destination_address="2 Rue Test",
            destination_country="France",
        )
        order.shipment = target_shipment
        order.save(update_fields=["shipment"])
        self._create_order_line(order=order, product=product, quantity=2)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        warmup = self.client.get(reverse("scan:scan_preparateur_order_prepare"))
        self.assertEqual(warmup.status_code, 200)
        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {
                "action": "mark_carton_ready",
                "carton_index": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        carton = Carton.objects.get()
        self.assertEqual(carton.shipment, target_shipment)
        self.assertNotEqual(carton.shipment, other_shipment)

    def test_mark_preparateur_plan_carton_ready_rejects_stale_order_plan(self):
        product = self._create_stock_product(
            sku="PREP-STALE",
            name="Produit Stale",
            quantity_on_hand=2,
        )
        current_order = self._create_order(
            association_name="Association Current",
            review_status=OrderReviewStatus.APPROVED,
        )
        stale_order = self._create_order(
            association_name="Association Stale",
            review_status=OrderReviewStatus.APPROVED,
        )
        stale_line = self._create_order_line(order=stale_order, product=product, quantity=1)

        with self.assertRaisesRegex(ValueError, "ne correspond pas"):
            mark_preparateur_plan_carton_ready(
                user=self.staff_user,
                order=current_order,
                plan={
                    "order_id": stale_order.id,
                    "carton_size": {
                        "length_cm": 40,
                        "width_cm": 30,
                        "height_cm": 30,
                        "max_weight_g": 8000,
                    },
                    "cartons": [
                        {
                            "index": 1,
                            "family": "MM",
                            "status": "pending",
                            "items": [
                                {
                                    "line_id": stale_line.id,
                                    "product_name": product.name,
                                    "quantity": 1,
                                    "location_label": "-",
                                }
                            ],
                        }
                    ],
                },
                carton_index=1,
            )

    def test_scan_preparateur_order_prepare_redirects_non_preparateur_to_orders_view(self):
        response = self.client.get(reverse("scan:scan_preparateur_order_prepare"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_orders_view"))

    def test_scan_preparateur_order_prepare_redirects_without_selected_order(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)

        response = self.client.get(reverse("scan:scan_preparateur_order_prepare"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("scan:scan_preparateur_order_select"))

    def test_scan_preparateur_order_prepare_handles_mark_ready_error(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-ERR",
            name="Produit Erreur",
            quantity_on_hand=10,
        )
        order = self._create_order(
            association_name="Association Error",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=1)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        response = self.client.post(
            reverse("scan:scan_preparateur_order_prepare"),
            {"action": "mark_carton_ready", "carton_index": "invalid"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid literal for int()")

    def test_scan_preparateur_order_prepare_picking_redirects_non_preparateur_or_without_order(
        self,
    ):
        non_preparateur_response = self.client.get(
            reverse("scan:scan_preparateur_order_prepare_picking")
        )
        self.assertEqual(non_preparateur_response.status_code, 302)
        self.assertEqual(
            non_preparateur_response["Location"],
            reverse("scan:scan_orders_view"),
        )

        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        no_order_response = self.client.get(reverse("scan:scan_preparateur_order_prepare_picking"))
        self.assertEqual(no_order_response.status_code, 302)
        self.assertEqual(
            no_order_response["Location"],
            reverse("scan:scan_preparateur_order_select"),
        )

    def test_scan_preparateur_order_prepare_picking_renders_with_selected_order(self):
        preparateur = self._create_preparateur()
        self.client.force_login(preparateur)
        product = self._create_stock_product(
            sku="PREP-PICKING",
            name="Produit Picking",
            quantity_on_hand=4,
        )
        order = self._create_order(
            association_name="Association Picking",
            review_status=OrderReviewStatus.APPROVED,
        )
        self._create_order_line(order=order, product=product, quantity=2)
        session = self.client.session
        session["preparateur_selected_order_id"] = order.id
        session.save()

        warmup = self.client.get(reverse("scan:scan_preparateur_order_prepare"))
        self.assertEqual(warmup.status_code, 200)

        response = self.client.get(reverse("scan:scan_preparateur_order_prepare_picking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produit Picking")
        self.assertContains(response, "Quantité")

    def test_preparateur_order_helpers_cover_session_and_early_return_branches(self):
        product = self._create_stock_product(
            sku="PREP-HELPER",
            name="Produit Helper",
            quantity_on_hand=2,
        )
        pending_order = self._create_order(
            association_name="Association Pending Helper",
            review_status=OrderReviewStatus.PENDING,
        )
        self._create_order_line(order=pending_order, product=product, quantity=1)

        request = mock.Mock()
        request.session = {
            "preparateur_selected_order_id": pending_order.id,
            "preparateur_order_plan": {"cartons": "invalid"},
        }

        self.assertIsNone(get_preparateur_order_plan(request))
        self.assertIsNone(get_preparateur_selected_order(request))
        self.assertNotIn("preparateur_selected_order_id", request.session)
        self.assertIsNone(build_preparateur_selected_order_summary(None))
        self.assertEqual(
            build_preparateur_order_picking_context(
                {"cartons": [{"items": []}, {"label": "Colis 2", "items": []}]}
            ),
            {
                "carton_blocks": [
                    {"carton_code": "-", "item_rows": []},
                    {"carton_code": "Colis 2", "item_rows": []},
                ],
                "picking_title": "Liste picking - commande",
            },
        )
        self.assertEqual(
            mark_preparateur_plan_carton_ready(
                user=self.staff_user,
                order=pending_order,
                plan={
                    "cartons": [
                        {
                            "index": 1,
                            "status": "ready",
                            "carton_id": 777,
                            "items": [],
                        }
                    ]
                },
                carton_index=1,
            ),
            777,
        )
