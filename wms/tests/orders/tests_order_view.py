from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from contacts.models import Contact
from wms.models import (
    Order,
    OrderDocumentType,
    OrderReviewStatus,
    OrderStatus,
    Shipment,
    ShipmentStatus,
)
from wms.order_view_handlers import handle_order_detail_action, handle_orders_view_action
from wms.order_view_helpers import build_order_detail_payload, build_orders_view_rows


class OrderViewHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _create_order(
        self,
        *,
        review_status=OrderReviewStatus.PENDING,
        status=OrderStatus.DRAFT,
        shipment=None,
    ):
        return Order.objects.create(
            status=status,
            review_status=review_status,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
            shipment=shipment,
        )

    def _create_shipment(self):
        return Shipment.objects.create(
            shipper_name="ASF",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def test_handle_orders_view_action_redirects_when_order_is_missing(self):
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "update_status", "order_id": "999"},
        )
        with mock.patch("wms.order_view_handlers.messages.error") as error_mock:
            response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        error_mock.assert_called_once_with(request, "Commande introuvable.")

    def test_handle_orders_view_action_rejects_invalid_review_status(self):
        order = self._create_order()
        request = self.factory.post(
            "/scan/orders-view/",
            {
                "action": "update_status",
                "order_id": str(order.id),
                "review_status": "invalid",
            },
        )
        with mock.patch("wms.order_view_handlers.messages.error") as error_mock:
            response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        error_mock.assert_called_once_with(request, "Statut invalide.")
        order.refresh_from_db()
        self.assertEqual(order.review_status, OrderReviewStatus.PENDING)

    def test_handle_orders_view_action_updates_review_status(self):
        order = self._create_order(review_status=OrderReviewStatus.PENDING)
        request = self.factory.post(
            "/scan/orders-view/",
            {
                "action": "update_status",
                "order_id": str(order.id),
                "review_status": OrderReviewStatus.APPROVED,
            },
        )
        with mock.patch("wms.order_view_handlers.messages.success") as success_mock:
            response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.review_status, OrderReviewStatus.APPROVED)
        self.assertIsNotNone(order.reviewed_at)
        success_mock.assert_called_once_with(request, "Statut de validation mis à jour.")

    def test_handle_orders_view_action_rejects_shipment_creation_when_not_approved(self):
        order = self._create_order(review_status=OrderReviewStatus.PENDING)
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "create_shipment", "order_id": str(order.id)},
        )
        with mock.patch("wms.order_view_handlers.messages.error") as error_mock:
            response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        error_mock.assert_called_once_with(request, "Commande non validée.")

    def test_handle_orders_view_action_creates_shipment_and_attaches_documents(self):
        order = self._create_order(review_status=OrderReviewStatus.APPROVED)
        generated_shipment = SimpleNamespace(id=321)
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "create_shipment", "order_id": str(order.id)},
        )
        with mock.patch(
            "wms.order_view_handlers.create_shipment_for_order",
            return_value=generated_shipment,
        ) as create_mock:
            with mock.patch(
                "wms.order_view_handlers.attach_order_documents_to_shipment"
            ) as attach_mock:
                response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        create_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, generated_shipment)
        self.assertEqual(response.url, "/scan/shipment/321/edit/")

    def test_handle_orders_view_action_reuses_legacy_pointer_from_scan_button(self):
        shipment = self._create_shipment()
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "create_shipment", "order_id": str(order.id)},
        )
        with mock.patch(
            "wms.order_view_handlers.create_shipment_for_order",
            return_value=shipment,
        ) as create_mock:
            with mock.patch(
                "wms.order_view_handlers.attach_order_documents_to_shipment"
            ) as attach_mock:
                response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertEqual(response.status_code, 302)
        create_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, shipment)
        self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")

    def test_handle_orders_view_action_reuses_existing_shipment_from_scan_button(self):
        shipment = self._create_shipment()
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            shipment=shipment,
        )
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "create_shipment", "order_id": str(order.id)},
        )

        with mock.patch(
            "wms.order_view_handlers.create_shipment_for_order",
            return_value=shipment,
        ) as create_mock:
            with mock.patch(
                "wms.order_view_handlers.attach_order_documents_to_shipment"
            ) as attach_mock:
                response = handle_orders_view_action(request, orders_qs=Order.objects.all())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")
        create_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, shipment)

    def test_handle_orders_view_action_returns_none_for_unknown_action(self):
        order = self._create_order()
        request = self.factory.post(
            "/scan/orders-view/",
            {"action": "unknown", "order_id": str(order.id)},
        )
        response = handle_orders_view_action(request, orders_qs=Order.objects.all())
        self.assertIsNone(response)

    def test_handle_order_detail_action_updates_review_status(self):
        order = self._create_order(review_status=OrderReviewStatus.PENDING)
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {
                "action": "update_status",
                "review_status": OrderReviewStatus.APPROVED,
            },
        )

        with mock.patch("wms.order_view_handlers.messages.success") as success_mock:
            response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/orders/{order.id}/")
        order.refresh_from_db()
        self.assertEqual(order.review_status, OrderReviewStatus.APPROVED)
        self.assertIsNotNone(order.reviewed_at)
        success_mock.assert_called_once_with(request, "Statut de validation mis à jour.")

    def test_handle_order_detail_action_rejects_shipment_creation_when_not_approved(self):
        order = self._create_order(review_status=OrderReviewStatus.PENDING)
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {"action": "create_shipment"},
        )

        with mock.patch("wms.order_view_handlers.messages.error") as error_mock:
            response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/orders/{order.id}/")
        error_mock.assert_called_once_with(request, "Commande non validée.")

    def test_handle_order_detail_action_creates_shipment_and_attaches_documents(self):
        order = self._create_order(review_status=OrderReviewStatus.APPROVED)
        generated_shipment = SimpleNamespace(id=654)
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {"action": "create_shipment"},
        )

        with mock.patch(
            "wms.order_view_handlers.create_shipment_for_order",
            return_value=generated_shipment,
        ) as create_mock:
            with mock.patch(
                "wms.order_view_handlers.attach_order_documents_to_shipment"
            ) as attach_mock:
                response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/scan/shipment/654/edit/")
        create_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, generated_shipment)

    def test_handle_order_detail_action_reuses_existing_shipment_from_scan_button(self):
        shipment = self._create_shipment()
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            shipment=shipment,
        )
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {"action": "create_shipment"},
        )

        with mock.patch(
            "wms.order_view_handlers.create_shipment_for_order",
            return_value=shipment,
        ) as create_mock:
            with mock.patch(
                "wms.order_view_handlers.attach_order_documents_to_shipment"
            ) as attach_mock:
                response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")
        create_mock.assert_called_once_with(order=order)
        attach_mock.assert_called_once_with(order, shipment)

    def test_handle_order_detail_action_requests_multi_shipment_confirmation_above_ten_cartons(
        self,
    ):
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {"action": "create_shipment_and_cartons"},
        )
        request.user = SimpleNamespace(username="scan-order-handler")

        with mock.patch(
            "wms.order_view_handlers.estimate_order_preparation_carton_count",
            return_value=(32, []),
        ):
            response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/orders/{order.id}/?prepare_confirm=1")

    def test_handle_order_detail_action_prepares_with_confirmed_shipment_count_and_warnings(self):
        shipment = self._create_shipment()
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
            shipment=shipment,
        )
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {
                "action": "create_shipment_and_cartons",
                "multi_shipment_confirmed": "1",
                "shipment_count": "4",
                "cartons_per_shipment": ["7", "10", "5", "10"],
            },
        )
        request.user = SimpleNamespace(username="scan-order-handler")

        def _prepare_order(**kwargs):
            kwargs["packing_warnings"].append("Produit test: poids/volume manquants.")
            return 0

        with mock.patch(
            "wms.order_view_handlers.estimate_order_preparation_carton_count",
            return_value=(32, []),
        ):
            with mock.patch(
                "wms.order_view_handlers.prepare_order",
                side_effect=_prepare_order,
            ) as prepare_mock:
                with mock.patch("wms.order_view_handlers.messages.warning") as warning_mock:
                    with mock.patch("wms.order_view_handlers.messages.success"):
                        response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")
        self.assertEqual(prepare_mock.call_args.kwargs["shipment_count"], 4)
        self.assertEqual(
            prepare_mock.call_args.kwargs["shipment_carton_counts"],
            [7, 10, 5, 10],
        )
        warning_mock.assert_called_once_with(
            request,
            "Produit test: poids/volume manquants.",
        )

    def test_handle_order_detail_action_uses_distribution_count_when_shipment_count_is_stale(
        self,
    ):
        for carton_counts, expected_shipment_count in ((["14"], 1), (["10", "4"], 2)):
            with self.subTest(carton_counts=carton_counts):
                shipment = self._create_shipment()
                order = self._create_order(
                    review_status=OrderReviewStatus.APPROVED,
                    status=OrderStatus.RESERVED,
                    shipment=shipment,
                )
                request = self.factory.post(
                    f"/scan/orders/{order.id}/",
                    {
                        "action": "create_shipment_and_cartons",
                        "multi_shipment_confirmed": "1",
                        "shipment_count": "3",
                        "cartons_per_shipment": carton_counts,
                    },
                )
                request.user = SimpleNamespace(username="scan-order-handler")

                with mock.patch(
                    "wms.order_view_handlers.estimate_order_preparation_carton_count",
                    return_value=(14, []),
                ):
                    with mock.patch("wms.order_view_handlers.prepare_order") as prepare_mock:
                        with mock.patch("wms.order_view_handlers.messages.success"):
                            response = handle_order_detail_action(request, order=order)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")
                self.assertEqual(
                    prepare_mock.call_args.kwargs["shipment_count"],
                    expected_shipment_count,
                )
                self.assertEqual(
                    prepare_mock.call_args.kwargs["shipment_carton_counts"],
                    [int(value) for value in carton_counts],
                )

    def test_handle_order_detail_action_rejects_distribution_when_total_does_not_match(self):
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
        )
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {
                "action": "create_shipment_and_cartons",
                "multi_shipment_confirmed": "1",
                "shipment_count": "4",
                "cartons_per_shipment": ["7", "10", "5", "9"],
            },
        )
        request.user = SimpleNamespace(username="scan-order-handler")

        with mock.patch(
            "wms.order_view_handlers.estimate_order_preparation_carton_count",
            return_value=(32, []),
        ):
            with mock.patch("wms.order_view_handlers.prepare_order") as prepare_mock:
                with mock.patch("wms.order_view_handlers.messages.error") as error_mock:
                    response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/orders/{order.id}/?prepare_confirm=1")
        prepare_mock.assert_not_called()
        error_mock.assert_called_once_with(
            request,
            "La répartition indique 31 colis au lieu de 32.",
        )

    def test_handle_order_detail_action_prepares_order_and_redirects_to_shipment(self):
        shipment = self._create_shipment()
        order = self._create_order(
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
            shipment=shipment,
        )
        request = self.factory.post(
            f"/scan/orders/{order.id}/",
            {"action": "create_shipment_and_cartons"},
        )
        request.user = SimpleNamespace(username="scan-order-handler")

        with mock.patch("wms.order_view_handlers.prepare_order", return_value=2) as prepare_mock:
            with mock.patch("wms.order_view_handlers.messages.success") as success_mock:
                response = handle_order_detail_action(request, order=order)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/scan/shipment/{shipment.id}/edit/")
        self.assertEqual(prepare_mock.call_args.kwargs["user"], request.user)
        self.assertEqual(prepare_mock.call_args.kwargs["order"], order)
        self.assertEqual(prepare_mock.call_args.kwargs["shipment_count"], 1)
        self.assertEqual(prepare_mock.call_args.kwargs["packing_warnings"], [])
        self.assertEqual(prepare_mock.call_args.kwargs["prepared_shipments"], [])
        success_mock.assert_called_once_with(
            request,
            "Préparation lancée: colis créés et rattachés à l'expédition.",
        )


class OrderViewHelpersTests(TestCase):
    def test_build_order_detail_payload_includes_prepare_confirmation(self):
        order = SimpleNamespace(
            association_contact=None,
            recipient_contact=None,
            recipient_name="Recipient",
            created_by=None,
            reference="CMD-32",
            id=32,
            created_at=None,
            review_status=OrderReviewStatus.APPROVED,
            status=OrderStatus.RESERVED,
            shipment_links=SimpleNamespace(all=lambda: []),
            documents=SimpleNamespace(all=lambda: []),
            lines=SimpleNamespace(
                select_related=lambda *_args: SimpleNamespace(all=lambda: []),
            ),
            shipper_contact=None,
            shipper_name="Shipper",
            destination_address="1 Rue Test",
            destination_city="Paris",
            destination_country="France",
        )

        with mock.patch(
            "wms.order_view_helpers.estimate_order_preparation_carton_count",
            return_value=(32, ["Produit test: poids/volume manquants."]),
        ):
            detail = build_order_detail_payload(order, include_prepare_confirmation=True)

        self.assertEqual(detail["prepare_confirmation"]["estimated_carton_count"], 32)
        self.assertEqual(detail["prepare_confirmation"]["recommended_shipment_count"], 4)
        self.assertEqual(
            detail["prepare_confirmation"]["default_carton_counts"],
            [10, 10, 10, 2],
        )
        self.assertEqual(
            detail["prepare_confirmation"]["warnings"],
            ["Produit test: poids/volume manquants."],
        )

    def test_build_orders_view_rows_maps_creator_and_filters_documents(self):
        association_contact = Contact.objects.create(name="Association Contact", is_active=True)
        creator = {"name": "Creator", "phone": "0102030405", "email": "creator@example.com"}

        wanted_doc = SimpleNamespace(
            doc_type=OrderDocumentType.DONATION_ATTESTATION,
            file=SimpleNamespace(url="/media/wanted.pdf"),
            get_doc_type_display=lambda: "Attestation donation",
        )
        ignored_type_doc = SimpleNamespace(
            doc_type=OrderDocumentType.OTHER,
            file=SimpleNamespace(url="/media/other.pdf"),
            get_doc_type_display=lambda: "Autre",
        )
        ignored_missing_file_doc = SimpleNamespace(
            doc_type=OrderDocumentType.HUMANITARIAN_ATTESTATION,
            file=None,
            get_doc_type_display=lambda: "Attestation aide humanitaire",
        )

        order = SimpleNamespace(
            association_contact=association_contact,
            recipient_contact=None,
            recipient_name="Fallback Name",
            documents=SimpleNamespace(
                all=lambda: [wanted_doc, ignored_type_doc, ignored_missing_file_doc]
            ),
        )

        with mock.patch(
            "wms.order_view_helpers.build_order_creator_info",
            return_value=creator,
        ):
            rows = build_orders_view_rows([order])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["association_name"], "Association Contact")
        self.assertEqual(rows[0]["creator"], creator)
        self.assertEqual(
            rows[0]["documents"],
            [{"label": "Attestation donation", "url": "/media/wanted.pdf"}],
        )

    def test_build_orders_view_rows_falls_back_to_recipient_name(self):
        order = SimpleNamespace(
            association_contact=None,
            recipient_contact=None,
            recipient_name="Recipient Fallback",
            review_status=OrderReviewStatus.PENDING,
            shipment=None,
            documents=SimpleNamespace(all=lambda: []),
        )

        with mock.patch(
            "wms.order_view_helpers.build_order_creator_info",
            return_value={"name": "-", "phone": "", "email": ""},
        ):
            rows = build_orders_view_rows([order])

        self.assertEqual(rows[0]["association_name"], "Recipient Fallback")
        self.assertEqual(rows[0]["documents"], [])

    def test_build_orders_view_rows_exposes_action_oriented_status_payloads(self):
        orders = [
            SimpleNamespace(
                association_contact=None,
                recipient_contact=None,
                recipient_name="Pending",
                review_status=OrderReviewStatus.PENDING,
                shipment=None,
                documents=SimpleNamespace(all=lambda: []),
            ),
            SimpleNamespace(
                association_contact=None,
                recipient_contact=None,
                recipient_name="Changes",
                review_status=OrderReviewStatus.CHANGES_REQUESTED,
                shipment=None,
                documents=SimpleNamespace(all=lambda: []),
            ),
            SimpleNamespace(
                association_contact=None,
                recipient_contact=None,
                recipient_name="Approved",
                review_status=OrderReviewStatus.APPROVED,
                shipment=None,
                documents=SimpleNamespace(all=lambda: []),
            ),
            SimpleNamespace(
                association_contact=None,
                recipient_contact=None,
                recipient_name="Rejected",
                review_status=OrderReviewStatus.REJECTED,
                shipment=SimpleNamespace(
                    status=ShipmentStatus.PLANNED,
                    is_disputed=False,
                ),
                documents=SimpleNamespace(all=lambda: []),
            ),
        ]

        with mock.patch(
            "wms.order_view_helpers.build_order_creator_info",
            return_value={"name": "Creator", "phone": "", "email": ""},
        ):
            rows = build_orders_view_rows(orders)

        self.assertEqual(rows[0]["review_status_display"]["label"], "En attente de validation")
        self.assertEqual(
            rows[0]["next_action_label"],
            "Valider ou demander des modifications",
        )
        self.assertIsNone(rows[0]["created_at"])
        self.assertEqual(rows[0]["open_url"], "")
        self.assertFalse(rows[0]["can_create_shipment"])
        self.assertEqual(rows[0]["shipment_status_display"]["label"], "-")

        self.assertEqual(rows[1]["next_action_label"], "Recontacter l'association")
        self.assertFalse(rows[1]["can_create_shipment"])

        self.assertEqual(rows[2]["next_action_label"], "Créer une expédition")
        self.assertTrue(rows[2]["can_create_shipment"])

        self.assertEqual(rows[3]["next_action_label"], "Expliquer le refus")
        self.assertFalse(rows[3]["can_create_shipment"])
        self.assertEqual(rows[3]["shipment_status_display"]["label"], "Planifié")
