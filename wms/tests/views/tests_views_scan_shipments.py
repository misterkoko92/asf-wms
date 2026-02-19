from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from wms.models import (
    Carton,
    Shipment,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
)


class ScanShipmentsViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-shipments-staff",
            password="pass1234",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def _render_stub(self, _request, template_name, context):
        response = HttpResponse(template_name)
        response.context_data = context
        return response

    def _create_shipment(self, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            status=status,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
            created_by=self.staff_user,
        )

    def test_scan_cartons_ready_short_circuits_when_handler_returns_response(self):
        with mock.patch(
            "wms.views_scan_shipments.handle_carton_status_update",
            return_value=HttpResponse("handled"),
        ):
            with mock.patch("wms.views_scan_shipments.get_carton_capacity_cm3") as capacity_mock:
                response = self.client.get(reverse("scan:scan_cartons_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "handled")
        capacity_mock.assert_not_called()

    def test_scan_cartons_ready_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.handle_carton_status_update",
            return_value=None,
        ):
            with mock.patch(
                "wms.views_scan_shipments.get_carton_capacity_cm3",
                return_value=12345,
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_cartons_ready_rows",
                    return_value=[{"id": 1, "code": "C-001"}],
                ) as rows_mock:
                    with mock.patch(
                        "wms.views_scan_shipments.render",
                        side_effect=self._render_stub,
                    ):
                        response = self.client.get(reverse("scan:scan_cartons_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/cartons_ready.html")
        self.assertEqual(response.context_data["active"], "cartons_ready")
        self.assertEqual(response.context_data["cartons"], [{"id": 1, "code": "C-001"}])
        self.assertEqual(rows_mock.call_args.kwargs["carton_capacity_cm3"], 12345)

    def test_scan_shipments_ready_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_ready_rows",
            return_value=[{"id": 1, "reference": "S-001"}],
        ):
            with mock.patch(
                "wms.views_scan_shipments.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_shipments_ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipments_ready.html")
        self.assertEqual(response.context_data["active"], "shipments_ready")
        self.assertEqual(
            response.context_data["shipments"],
            [{"id": 1, "reference": "S-001"}],
        )

    def test_scan_shipments_tracking_renders_rows_context(self):
        with mock.patch(
            "wms.views_scan_shipments.build_shipments_tracking_rows",
            return_value=[{"id": 1, "reference": "S-TRACK-001"}],
        ):
            with mock.patch(
                "wms.views_scan_shipments.render",
                side_effect=self._render_stub,
            ):
                response = self.client.get(reverse("scan:scan_shipments_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipments_tracking.html")
        self.assertEqual(response.context_data["active"], "shipments_tracking")
        self.assertEqual(
            response.context_data["shipments"],
            [{"id": 1, "reference": "S-TRACK-001"}],
        )
        self.assertEqual(response.context_data["closed_filter"], "exclude")

    def test_scan_shipments_tracking_post_closes_ready_shipment(self):
        shipment = self._create_shipment(status=ShipmentStatus.DELIVERED)
        for step in [
            ShipmentTrackingStatus.PLANNED,
            ShipmentTrackingStatus.BOARDING_OK,
            ShipmentTrackingStatus.RECEIVED_CORRESPONDENT,
            ShipmentTrackingStatus.RECEIVED_RECIPIENT,
        ]:
            ShipmentTrackingEvent.objects.create(
                shipment=shipment,
                status=step,
                actor_name="Agent",
                actor_structure="ASF",
                comments="ok",
                created_by=self.staff_user,
            )

        with mock.patch("wms.views_scan_shipments.log_shipment_case_closed") as log_mock:
            response = self.client.post(
                reverse("scan:scan_shipments_tracking"),
                {"action": "close_shipment_case", "shipment_id": shipment.id},
            )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertIsNotNone(shipment.closed_at)
        self.assertEqual(shipment.closed_by, self.staff_user)
        log_mock.assert_called_once_with(
            shipment=shipment,
            user=self.staff_user,
        )

    def test_scan_shipments_tracking_post_does_not_close_incomplete_shipment(self):
        shipment = self._create_shipment(status=ShipmentStatus.DELIVERED)
        ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.RECEIVED_RECIPIENT,
            actor_name="Agent",
            actor_structure="ASF",
            comments="partial",
            created_by=self.staff_user,
        )

        response = self.client.post(
            reverse("scan:scan_shipments_tracking"),
            {"action": "close_shipment_case", "shipment_id": shipment.id},
        )

        self.assertEqual(response.status_code, 302)
        shipment.refresh_from_db()
        self.assertIsNone(shipment.closed_at)
        self.assertIsNone(shipment.closed_by)

    def test_scan_pack_get_uses_session_pack_results_and_defaults(self):
        session = self.client.session
        session["pack_results"] = [10, 20]
        session.save()

        fake_form = object()
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[{"id": 1}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([{"id": 1, "name": "Std"}], "default-format"),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.build_packing_result",
                        return_value={"packed_count": 2},
                    ) as packing_result_mock:
                        with mock.patch(
                            "wms.views_scan_shipments.build_pack_defaults",
                            return_value=(
                                "1",
                                {"length_cm": 40},
                                2,
                                [{"line": 1}, {"line": 2}],
                            ),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(reverse("scan:scan_pack"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/pack.html")
        self.assertEqual(response.context_data["packing_result"], {"packed_count": 2})
        self.assertEqual(response.context_data["line_count"], 2)
        self.assertEqual(response.context_data["line_values"], [{"line": 1}, {"line": 2}])
        self.assertEqual(response.context_data["missing_defaults"], [])
        self.assertFalse(response.context_data["confirm_defaults"])
        packing_result_mock.assert_called_once_with([10, 20])

    def test_scan_pack_post_returns_handler_response_when_available(self):
        fake_form = object()
        pack_state = {
            "carton_format_id": "custom",
            "carton_custom": {"length_cm": 30},
            "line_count": 1,
            "line_values": [{"line": 1}],
            "line_errors": {},
        }
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([], None),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_pack_post",
                        return_value=(HttpResponse("pack-post"), pack_state),
                    ):
                        response = self.client.post(reverse("scan:scan_pack"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "pack-post")

    def test_scan_pack_post_renders_context_when_handler_has_no_response(self):
        fake_form = object()
        pack_state = {
            "carton_format_id": "1",
            "carton_custom": {"length_cm": 40},
            "line_count": 3,
            "line_values": [{"line": 1}],
            "line_errors": {"1": "invalid"},
            "missing_defaults": ["SKU-001"],
            "confirm_defaults": True,
        }
        with mock.patch(
            "wms.views_scan_shipments.ScanPackForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_product_options",
                return_value=[{"id": 1}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_formats",
                    return_value=([{"id": 1}], "default"),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_pack_post",
                        return_value=(None, pack_state),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.render",
                            side_effect=self._render_stub,
                        ):
                            response = self.client.post(reverse("scan:scan_pack"), {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/pack.html")
        self.assertEqual(response.context_data["line_count"], 3)
        self.assertEqual(response.context_data["line_errors"], {"1": "invalid"})
        self.assertEqual(response.context_data["missing_defaults"], ["SKU-001"])
        self.assertTrue(response.context_data["confirm_defaults"])

    def test_scan_shipment_create_get_builds_initial_line_values(self):
        fake_form = SimpleNamespace(initial={"carton_count": 2})
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", set()),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.build_shipment_line_values",
                        return_value=[{"line": 1}, {"line": 2}],
                    ) as line_values_mock:
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_context",
                            return_value={"context_key": "value"},
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(
                                    reverse("scan:scan_shipment_create")
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "value")
        self.assertEqual(response.context_data["active"], "shipment")
        line_values_mock.assert_called_once_with(2)

    def test_scan_shipment_create_post_returns_handler_response_when_available(self):
        fake_form = SimpleNamespace(initial={"carton_count": 1})
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", {1}),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_shipment_create_post",
                        return_value=(HttpResponse("created"), 1, [], {}),
                    ):
                        response = self.client.post(
                            reverse("scan:scan_shipment_create"), {}
                        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "created")

    def test_scan_shipment_create_post_renders_context_when_no_handler_response(self):
        fake_form = SimpleNamespace(initial={"carton_count": 1})
        with mock.patch(
            "wms.views_scan_shipments.ScanShipmentForm",
            return_value=fake_form,
        ):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_form_payload",
                return_value=([], [], [], [], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_carton_selection_data",
                    return_value=("[]", {1}),
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.handle_shipment_create_post",
                        return_value=(None, 3, [{"line": 1}], {"1": "err"}),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_context",
                            return_value={"context_key": "post"},
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.post(
                                    reverse("scan:scan_shipment_create"), {}
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "post")
        self.assertEqual(response.context_data["active"], "shipment")

    def test_scan_shipment_edit_redirects_when_shipment_is_not_editable(self):
        shipment = self._create_shipment(status=ShipmentStatus.SHIPPED)
        response = self.client.get(
            reverse("scan:scan_shipment_edit", kwargs={"shipment_id": shipment.id})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("scan:scan_shipments_ready"))

    def test_scan_shipment_edit_get_renders_context(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        carton = Carton.objects.create(code="C-EDIT-1", shipment=shipment)
        fake_form = object()
        initial = {"destination": "", "carton_count": 1}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[{"id": carton.id, "code": carton.code}],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", {carton.id}),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.build_shipment_edit_line_values",
                                    return_value=[{"line": 1}],
                                ):
                                    with mock.patch(
                                        "wms.views_scan_shipments.build_shipment_form_context",
                                        return_value={"context_key": "edit-get"},
                                    ):
                                        with mock.patch(
                                            "wms.views_scan_shipments.render",
                                            side_effect=self._render_stub,
                                        ):
                                            response = self.client.get(
                                                reverse(
                                                    "scan:scan_shipment_edit",
                                                    kwargs={"shipment_id": shipment.id},
                                                )
                                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "edit-get")
        self.assertTrue(response.context_data["is_edit"])
        self.assertEqual(response.context_data["shipment"].id, shipment.id)
        self.assertIn("tracking_url", response.context_data)
        self.assertEqual(response.context_data["carton_docs"], [{"id": carton.id, "code": carton.code}])

    def test_scan_shipment_edit_post_returns_handler_response_when_available(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        initial = {"destination": "", "carton_count": 1}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", set()),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.handle_shipment_edit_post",
                                    return_value=(HttpResponse("edited"), 1, [], {}),
                                ):
                                    response = self.client.post(
                                        reverse(
                                            "scan:scan_shipment_edit",
                                            kwargs={"shipment_id": shipment.id},
                                        ),
                                        {},
                                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "edited")

    def test_scan_shipment_edit_post_renders_context_when_no_handler_response(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        initial = {"destination": "", "carton_count": 2}

        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_carton_options",
                return_value=[],
            ):
                with mock.patch(
                    "wms.views_scan_shipments.build_shipment_edit_initial",
                    return_value=initial,
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ScanShipmentForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.build_shipment_form_payload",
                            return_value=([], [], [], [], [], []),
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.build_carton_selection_data",
                                return_value=("[]", set()),
                            ):
                                with mock.patch(
                                    "wms.views_scan_shipments.handle_shipment_edit_post",
                                    return_value=(None, 2, [{"line": 1}], {"1": "err"}),
                                ):
                                    with mock.patch(
                                        "wms.views_scan_shipments.build_shipment_form_context",
                                        return_value={"context_key": "edit-post"},
                                    ):
                                        with mock.patch(
                                            "wms.views_scan_shipments.render",
                                            side_effect=self._render_stub,
                                        ):
                                            response = self.client.post(
                                                reverse(
                                                    "scan:scan_shipment_edit",
                                                    kwargs={"shipment_id": shipment.id},
                                                ),
                                                {},
                                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_create.html")
        self.assertEqual(response.context_data["context_key"], "edit-post")
        self.assertTrue(response.context_data["is_edit"])

    def test_scan_shipment_track_get_renders_tracking_context(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        fake_form = object()
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=(["doc"], ["carton"], ["additional"]),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=fake_form,
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(
                                    reverse(
                                        "scan:scan_shipment_track",
                                        kwargs={"tracking_token": shipment.tracking_token},
                                    )
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_tracking.html")
        self.assertTrue(response.context_data["can_update_tracking"])
        self.assertEqual(response.context_data["documents"], ["doc"])
        self.assertEqual(response.context_data["carton_docs"], ["carton"])
        self.assertEqual(response.context_data["additional_docs"], ["additional"])
        self.assertIs(response.context_data["form"], fake_form)
        self.assertEqual(response.context_data["return_to"], "shipments_tracking")

    def test_scan_shipment_track_post_returns_handler_response(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=HttpResponse("tracking-post"),
                        ) as handler_mock:
                            response = self.client.post(
                                reverse(
                                    "scan:scan_shipment_track",
                                    kwargs={"tracking_token": shipment.tracking_token},
                                ),
                                {"status": "planning_ok"},
                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "tracking-post")
        self.assertFalse(handler_mock.call_args.kwargs["return_to_list"])
        self.assertIsNone(handler_mock.call_args.kwargs["return_to_view"])
        self.assertEqual(handler_mock.call_args.kwargs["return_to_key"], "shipments_tracking")

    def test_scan_shipment_track_post_passes_return_to_list_flag(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=HttpResponse("tracking-post"),
                        ) as handler_mock:
                            response = self.client.post(
                                reverse(
                                    "scan:scan_shipment_track",
                                    kwargs={"tracking_token": shipment.tracking_token},
                                ),
                                {"status": "planning_ok", "return_to_list": "1"},
                            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "tracking-post")
        self.assertTrue(handler_mock.call_args.kwargs["return_to_list"])
        self.assertEqual(
            handler_mock.call_args.kwargs["return_to_view"],
            "scan:scan_shipments_tracking",
        )
        self.assertEqual(handler_mock.call_args.kwargs["return_to_key"], "shipments_tracking")

    def test_scan_shipment_track_get_uses_ready_return_target(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=([], [], []),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.next_tracking_status",
                    return_value="planning_ok",
                ):
                    with mock.patch(
                        "wms.views_scan_shipments.ShipmentTrackingForm",
                        return_value=object(),
                    ):
                        with mock.patch(
                            "wms.views_scan_shipments.handle_shipment_tracking_post",
                            return_value=None,
                        ):
                            with mock.patch(
                                "wms.views_scan_shipments.render",
                                side_effect=self._render_stub,
                            ):
                                response = self.client.get(
                                    f"{reverse('scan:scan_shipment_track', kwargs={'tracking_token': shipment.tracking_token})}?return_to=shipments_ready"
                                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["return_to"], "shipments_ready")
        self.assertEqual(
            response.context_data["back_to_url"],
            reverse("scan:scan_shipments_ready"),
        )

    def test_scan_shipment_track_legacy_renders_read_only_tracking(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        with mock.patch("wms.views_scan_shipments.Shipment.ensure_qr_code"):
            with mock.patch(
                "wms.views_scan_shipments.build_shipment_document_links",
                return_value=(["doc"], ["carton"], ["additional"]),
            ):
                with mock.patch(
                    "wms.views_scan_shipments.render",
                    side_effect=self._render_stub,
                ):
                    response = self.client.get(
                        reverse(
                            "scan:scan_shipment_track_legacy",
                            kwargs={"shipment_ref": shipment.reference},
                        )
                    )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "scan/shipment_tracking.html")
        self.assertFalse(response.context_data["can_update_tracking"])
        self.assertIsNone(response.context_data["form"])
        self.assertEqual(response.context_data["tracking_url"], "")
        self.assertEqual(
            response["X-ASF-Legacy-Endpoint"],
            "shipment-track-by-reference; status=deprecated",
        )
        self.assertEqual(response["X-ASF-Legacy-Sunset"], "2026-06-30")

    @override_settings(ENABLE_SHIPMENT_TRACK_LEGACY=False)
    def test_scan_shipment_track_legacy_returns_404_when_feature_disabled(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        response = self.client.get(
            reverse(
                "scan:scan_shipment_track_legacy",
                kwargs={"shipment_ref": shipment.reference},
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_scan_shipment_track_legacy_returns_404_for_non_staff_user(self):
        shipment = self._create_shipment(status=ShipmentStatus.DRAFT)
        non_staff = get_user_model().objects.create_user(
            username="scan-shipments-non-staff",
            password="pass1234",
            is_staff=False,
        )
        self.client.force_login(non_staff)
        response = self.client.get(
            reverse(
                "scan:scan_shipment_track_legacy",
                kwargs={"shipment_ref": shipment.reference},
            )
        )
        self.assertEqual(response.status_code, 404)
