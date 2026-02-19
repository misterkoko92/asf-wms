from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from wms.models import CartonStatus, ShipmentStatus
from wms.scan_shipment_handlers import (
    _get_carton_count,
    handle_shipment_create_post,
    handle_shipment_edit_post,
)
from wms.services import StockError


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}
        self.errors = []

    def is_valid(self):
        return self._valid

    def add_error(self, field, error):
        self.errors.append((field, str(error)))


class ScanShipmentHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, username="scanner")

    def _request(self, data=None):
        request = self.factory.post("/scan/shipment/", data or {})
        request.user = self.user
        return request

    def _cleaned_data(self, *, carton_count=2):
        destination = SimpleNamespace(country="France")
        shipper = SimpleNamespace(name="ASF")
        recipient = SimpleNamespace(name="Association Dest")
        correspondent = SimpleNamespace(name="Correspondant")
        return {
            "carton_count": carton_count,
            "destination": destination,
            "shipper_contact": shipper,
            "recipient_contact": recipient,
            "correspondent_contact": correspondent,
        }

    def test_get_carton_count_uses_form_when_valid(self):
        request = self._request({"carton_count": "10"})
        form = _FakeForm(valid=True, cleaned_data={"carton_count": 4})
        self.assertEqual(_get_carton_count(form, request), 4)

    def test_get_carton_count_handles_invalid_values(self):
        form = _FakeForm(valid=False)
        self.assertEqual(_get_carton_count(form, self._request({"carton_count": "0"})), 1)
        self.assertEqual(_get_carton_count(form, self._request({"carton_count": "bad"})), 1)

    def test_handle_shipment_create_post_success(self):
        request = self._request({"carton_count": "2"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=2))
        shipment = SimpleNamespace(reference="S-001")
        carton = SimpleNamespace(shipment=None, save=mock.Mock())
        carton_query = mock.MagicMock()
        carton_query.select_for_update.return_value = carton_query
        carton_query.first.return_value = carton

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [{"line": 1}],
                [{"carton_id": 10}, {"product": "P", "quantity": 3}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Shipment.objects.create",
                    return_value=shipment,
                ):
                    with mock.patch(
                        "wms.scan_shipment_handlers.Carton.objects.filter",
                        return_value=carton_query,
                    ):
                        with mock.patch(
                            "wms.scan_shipment_handlers.pack_carton"
                        ) as pack_mock:
                            with mock.patch(
                                "wms.scan_shipment_handlers.sync_shipment_ready_state"
                            ) as sync_mock:
                                with mock.patch(
                                    "wms.scan_shipment_handlers.messages.success"
                                ):
                                    with mock.patch(
                                        "wms.scan_shipment_handlers.redirect",
                                        return_value=SimpleNamespace(status_code=302, url="/next"),
                                    ) as redirect_mock:
                                        with mock.patch(
                                            "wms.scan_shipment_handlers.connection",
                                            SimpleNamespace(
                                                features=SimpleNamespace(
                                                    has_select_for_update=True
                                                )
                                            ),
                                        ):
                                            response, carton_count, line_values, line_errors = (
                                                handle_shipment_create_post(
                                                    request,
                                                    form=form,
                                                    available_carton_ids={10},
                                                )
                                            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(carton_count, 2)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        carton.save.assert_called_once_with(update_fields=["shipment", "status"])
        pack_mock.assert_called_once()
        sync_mock.assert_called_once_with(shipment)
        redirect_mock.assert_called_once_with("scan:scan_shipment_create")

    def test_handle_shipment_create_post_adds_form_error_on_unavailable_carton(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(reference="S-002")
        carton_query = mock.MagicMock()
        carton_query.first.return_value = None

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 22}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Shipment.objects.create",
                    return_value=shipment,
                ):
                    with mock.patch(
                        "wms.scan_shipment_handlers.Carton.objects.filter",
                        return_value=carton_query,
                    ):
                        response, _count, _lines, _errors = handle_shipment_create_post(
                            request,
                            form=form,
                            available_carton_ids={22},
                        )

        self.assertIsNone(response)
        self.assertIn((None, "Carton indisponible."), form.errors)

    def test_handle_shipment_create_post_skips_processing_when_line_errors_present(self):
        request = self._request({"carton_count": "3"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=3))

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": "invalid"}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Shipment.objects.create"
            ) as create_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertIsNone(response)
        self.assertEqual(carton_count, 3)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {"1": "invalid"})
        create_mock.assert_not_called()

    def test_handle_shipment_create_post_save_draft_ignores_line_errors(self):
        request = self._request({"action": "save_draft", "carton_count": "1"})
        form = _FakeForm(valid=False)
        expected_response = SimpleNamespace(status_code=302, url="/shipment/1/edit")

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": ["missing"]}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers._handle_shipment_save_draft_post",
                return_value=expected_response,
            ) as save_draft_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertEqual(response, expected_response)
        self.assertEqual(carton_count, 1)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        save_draft_mock.assert_called_once_with(
            request,
            form=form,
            redirect_to_pack=False,
        )

    def test_handle_shipment_create_post_save_draft_pack_redirects_to_pack_flow(self):
        request = self._request({"action": "save_draft_pack", "carton_count": "1"})
        form = _FakeForm(valid=False)
        expected_response = SimpleNamespace(status_code=302, url="/scan/pack/")

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {"1": ["missing"]}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers._handle_shipment_save_draft_post",
                return_value=expected_response,
            ) as save_draft_mock:
                response, carton_count, line_values, line_errors = handle_shipment_create_post(
                    request,
                    form=form,
                    available_carton_ids=set(),
                )

        self.assertEqual(response, expected_response)
        self.assertEqual(carton_count, 1)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        save_draft_mock.assert_called_once_with(
            request,
            form=form,
            redirect_to_pack=True,
        )

    def test_handle_shipment_edit_post_success(self):
        request = self._request({"carton_count": "2"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=2))
        shipment = SimpleNamespace(
            id=50,
            reference="S-EDIT-001",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        carton_to_remove = SimpleNamespace(
            status=CartonStatus.PACKED, shipment=shipment, save=mock.Mock()
        )
        shipment.carton_set.exclude.return_value = [carton_to_remove]
        selected_carton = SimpleNamespace(
            shipment_id=None,
            shipment=None,
            status=CartonStatus.PACKED,
            save=mock.Mock(),
        )
        carton_query = mock.MagicMock()
        carton_query.select_for_update.return_value = carton_query
        carton_query.first.return_value = selected_carton

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=(
                [{"line": 1}],
                [{"carton_id": 99}, {"product": "P", "quantity": 1}],
                {},
            ),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.build_destination_label",
                return_value="Paris - France",
            ):
                with mock.patch(
                    "wms.scan_shipment_handlers.Carton.objects.filter",
                    return_value=carton_query,
                ):
                    with mock.patch(
                        "wms.scan_shipment_handlers.pack_carton"
                    ) as pack_mock:
                        with mock.patch(
                            "wms.scan_shipment_handlers.sync_shipment_ready_state"
                        ) as sync_mock:
                            with mock.patch(
                                "wms.scan_shipment_handlers.messages.success"
                            ):
                                with mock.patch(
                                    "wms.scan_shipment_handlers.redirect",
                                    return_value=SimpleNamespace(status_code=302, url="/ready"),
                                ) as redirect_mock:
                                    with mock.patch(
                                        "wms.scan_shipment_handlers.connection",
                                        SimpleNamespace(
                                            features=SimpleNamespace(
                                                has_select_for_update=True
                                            )
                                        ),
                                    ):
                                        response, carton_count, line_values, line_errors = (
                                            handle_shipment_edit_post(
                                                request,
                                                form=form,
                                                shipment=shipment,
                                                allowed_carton_ids={99},
                                            )
                                        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(carton_count, 2)
        self.assertEqual(line_values, [{"line": 1}])
        self.assertEqual(line_errors, {})
        shipment.save.assert_called_once()
        carton_to_remove.save.assert_called_once_with(update_fields=["shipment"])
        selected_carton.save.assert_called_once_with(update_fields=["shipment", "status"])
        pack_mock.assert_called_once()
        sync_mock.assert_called_once_with(shipment)
        redirect_mock.assert_called_once_with("scan:scan_shipments_ready")

    def test_handle_shipment_edit_post_rejects_removal_of_shipped_carton(self):
        request = self._request({"carton_count": "1"})
        form = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=51,
            reference="S-EDIT-002",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        shipment.carton_set.exclude.return_value = [
            SimpleNamespace(status=CartonStatus.SHIPPED)
        ]

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [], {}),
        ):
            response, _count, _lines, _errors = handle_shipment_edit_post(
                request,
                form=form,
                shipment=shipment,
                allowed_carton_ids=set(),
            )

        self.assertIsNone(response)
        self.assertIn((None, "Impossible de retirer un carton expédié."), form.errors)

    def test_handle_shipment_edit_post_rejects_missing_or_unavailable_selected_carton(self):
        request = self._request({"carton_count": "1"})
        form_missing = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        shipment = SimpleNamespace(
            id=52,
            reference="S-EDIT-003",
            status=ShipmentStatus.DRAFT,
            carton_set=mock.MagicMock(),
            save=mock.Mock(),
        )
        shipment.carton_set.exclude.return_value = []
        missing_query = mock.MagicMock()
        missing_query.first.return_value = None

        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 123}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Carton.objects.filter",
                return_value=missing_query,
            ):
                response, *_ = handle_shipment_edit_post(
                    request,
                    form=form_missing,
                    shipment=shipment,
                    allowed_carton_ids={123},
                )
        self.assertIsNone(response)
        self.assertIn((None, "Carton introuvable."), form_missing.errors)

        form_unavailable = _FakeForm(valid=True, cleaned_data=self._cleaned_data(carton_count=1))
        unavailable_query = mock.MagicMock()
        unavailable_query.first.return_value = SimpleNamespace(
            shipment_id=999, shipment=None, status=CartonStatus.PACKED, save=mock.Mock()
        )
        with mock.patch(
            "wms.scan_shipment_handlers.parse_shipment_lines",
            return_value=([{"line": 1}], [{"carton_id": 123}], {}),
        ):
            with mock.patch(
                "wms.scan_shipment_handlers.Carton.objects.filter",
                return_value=unavailable_query,
            ):
                response, *_ = handle_shipment_edit_post(
                    request,
                    form=form_unavailable,
                    shipment=shipment,
                    allowed_carton_ids={123},
                )
        self.assertIsNone(response)
        self.assertIn((None, "Carton indisponible."), form_unavailable.errors)
