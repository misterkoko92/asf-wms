from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from wms.models import ReceiptStatus, ReceiptType
from wms.receipt_handlers import (
    build_hors_format_lines,
    get_receipt_lines_state,
    handle_receipt_action,
    handle_receipt_association_post,
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


class ReceiptHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, username="receipt-user")

    def _request(self, data=None):
        request = self.factory.post("/scan/receive/", data or {})
        request.user = self.user
        return request

    def test_get_receipt_lines_state_handles_none_and_counts_pending(self):
        self.assertEqual(get_receipt_lines_state(None), ([], 0))

        lines = [
            SimpleNamespace(received_lot_id=None),
            SimpleNamespace(received_lot_id=12),
            SimpleNamespace(received_lot_id=None),
        ]
        receipt = SimpleNamespace(
            lines=SimpleNamespace(
                select_related=lambda *args, **kwargs: SimpleNamespace(all=lambda: lines)
            )
        )
        receipt_lines, pending = get_receipt_lines_state(receipt)
        self.assertEqual(receipt_lines, lines)
        self.assertEqual(pending, 2)

    def test_build_hors_format_lines_parses_count_and_descriptions(self):
        request = self._request(
            {
                "hors_format_count": "2",
                "line_1_description": "  Materiel A ",
                "line_2_description": "",
            }
        )
        count, values = build_hors_format_lines(request)
        self.assertEqual(count, 2)
        self.assertEqual(values, [{"description": "Materiel A"}, {"description": ""}])

        request_invalid = self._request({"hors_format_count": "-1"})
        count_invalid, values_invalid = build_hors_format_lines(request_invalid)
        self.assertEqual(count_invalid, 0)
        self.assertEqual(values_invalid, [])

    def test_handle_receipt_association_post_validates_missing_line_descriptions(self):
        form = _FakeForm(valid=True)
        request = self._request()
        response, line_errors = handle_receipt_association_post(
            request,
            create_form=form,
            line_values=[{"description": ""}],
            line_count=1,
        )
        self.assertIsNone(response)
        self.assertEqual(line_errors, {"1": ["Description requise."]})
        self.assertIn((None, "Renseignez les descriptions hors format."), form.errors)

    def test_handle_receipt_association_post_requires_default_warehouse(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "source_contact": None,
                "carrier_contact": None,
                "received_on": None,
                "carton_count": 3,
            },
        )
        request = self._request()
        with mock.patch("wms.receipt_handlers.resolve_default_warehouse", return_value=None):
            response, line_errors = handle_receipt_association_post(
                request,
                create_form=form,
                line_values=[{"description": "HF"}],
                line_count=1,
            )
        self.assertIsNone(response)
        self.assertEqual(line_errors, {})
        self.assertIn((None, "Aucun entrepôt configuré."), form.errors)

    def test_handle_receipt_association_post_success_creates_receipt_and_lines(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "source_contact": "source",
                "carrier_contact": "carrier",
                "received_on": "2026-01-10",
                "carton_count": 2,
            },
        )
        request = self._request()
        receipt = SimpleNamespace(reference="RCP-001")
        with mock.patch(
            "wms.receipt_handlers.resolve_default_warehouse",
            return_value=SimpleNamespace(id=1),
        ):
            with mock.patch(
                "wms.receipt_handlers.Receipt.objects.create",
                return_value=receipt,
            ) as receipt_create_mock:
                with mock.patch(
                    "wms.receipt_handlers.ReceiptHorsFormat.objects.create"
                ) as hors_mock:
                    with mock.patch("wms.receipt_handlers.messages.success") as success_mock:
                        response, line_errors = handle_receipt_association_post(
                            request,
                            create_form=form,
                            line_values=[{"description": "HF1"}, {"description": "HF2"}],
                            line_count=2,
                        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(line_errors, {})
        receipt_create_mock.assert_called_once()
        self.assertEqual(hors_mock.call_count, 2)
        success_mock.assert_called_once()

    def test_handle_receipt_action_select_receipt_redirects(self):
        receipt = SimpleNamespace(id=10)
        select_form = _FakeForm(valid=True, cleaned_data={"receipt": receipt})
        response, lines, pending = handle_receipt_action(
            self._request({"action": "select_receipt"}),
            action="select_receipt",
            select_form=select_form,
            create_form=_FakeForm(valid=False),
            line_form=_FakeForm(valid=False),
            selected_receipt=None,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        self.assertTrue(response.url.endswith("?receipt=10"))

    def test_handle_receipt_action_create_receipt_redirects(self):
        create_form = _FakeForm(
            valid=True,
            cleaned_data={
                "receipt_type": ReceiptType.DONATION,
                "source_contact": "source",
                "carrier_contact": "carrier",
                "origin_reference": "orig",
                "carrier_reference": "car",
                "received_on": "2026-01-10",
                "warehouse": "warehouse",
                "notes": "note",
            },
        )
        created_receipt = SimpleNamespace(id=42, reference="RCP-042")
        with mock.patch(
            "wms.receipt_handlers.Receipt.objects.create",
            return_value=created_receipt,
        ) as create_mock:
            with mock.patch("wms.receipt_handlers.messages.success"):
                response, lines, pending = handle_receipt_action(
                    self._request({"action": "create_receipt"}),
                    action="create_receipt",
                    select_form=_FakeForm(valid=False),
                    create_form=create_form,
                    line_form=_FakeForm(valid=False),
                    selected_receipt=None,
                )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        self.assertTrue(response.url.endswith("?receipt=42"))
        create_mock.assert_called_once()

    def test_handle_receipt_action_add_line_requires_selected_receipt(self):
        line_form = _FakeForm(valid=True, cleaned_data={})
        response, lines, pending = handle_receipt_action(
            self._request({"action": "add_line"}),
            action="add_line",
            select_form=_FakeForm(valid=False),
            create_form=_FakeForm(valid=False),
            line_form=line_form,
            selected_receipt=None,
        )
        self.assertIsNone(response)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        self.assertIn((None, "Sélectionnez une réception."), line_form.errors)

    def test_handle_receipt_action_add_line_rejects_closed_receipt(self):
        line_form = _FakeForm(valid=True, cleaned_data={})
        selected_receipt = SimpleNamespace(status=ReceiptStatus.RECEIVED)
        response, lines, pending = handle_receipt_action(
            self._request({"action": "add_line"}),
            action="add_line",
            select_form=_FakeForm(valid=False),
            create_form=_FakeForm(valid=False),
            line_form=line_form,
            selected_receipt=selected_receipt,
        )
        self.assertIsNone(response)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        self.assertIn((None, "Réception déjà clôturée."), line_form.errors)

    def test_handle_receipt_action_add_line_validates_product_and_location(self):
        selected_receipt = SimpleNamespace(
            id=3,
            status=ReceiptStatus.DRAFT,
            lines=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(quantity=kwargs["quantity"])),
        )
        line_form_missing_product = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "UNKNOWN",
                "location": None,
                "quantity": 2,
                "lot_code": "",
                "expires_on": None,
                "lot_status": "",
                "storage_conditions": "",
                "receive_now": False,
            },
        )
        with mock.patch("wms.receipt_handlers.resolve_product", return_value=None):
            response, *_ = handle_receipt_action(
                self._request({"action": "add_line"}),
                action="add_line",
                select_form=_FakeForm(valid=False),
                create_form=_FakeForm(valid=False),
                line_form=line_form_missing_product,
                selected_receipt=selected_receipt,
            )
        self.assertIsNone(response)
        self.assertIn(("product_code", "Produit introuvable."), line_form_missing_product.errors)

        product = SimpleNamespace(default_location=None, storage_conditions="Cold", name="Mask")
        line_form_missing_location = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "MASK",
                "location": None,
                "quantity": 2,
                "lot_code": "",
                "expires_on": None,
                "lot_status": "",
                "storage_conditions": "",
                "receive_now": False,
            },
        )
        with mock.patch("wms.receipt_handlers.resolve_product", return_value=product):
            response, *_ = handle_receipt_action(
                self._request({"action": "add_line"}),
                action="add_line",
                select_form=_FakeForm(valid=False),
                create_form=_FakeForm(valid=False),
                line_form=line_form_missing_location,
                selected_receipt=selected_receipt,
            )
        self.assertIsNone(response)
        self.assertIn(
            ("location", "Emplacement requis ou définir un emplacement par défaut."),
            line_form_missing_location.errors,
        )

    def test_handle_receipt_action_add_line_success_and_receive_now_error_path(self):
        line_model = SimpleNamespace(quantity=2)
        selected_receipt = SimpleNamespace(
            id=4,
            status=ReceiptStatus.DRAFT,
            lines=SimpleNamespace(create=lambda **kwargs: line_model),
        )
        location = SimpleNamespace(id=1)
        product = SimpleNamespace(default_location=location, storage_conditions="Cold", name="Mask")
        base_cleaned = {
            "product_code": "MASK",
            "location": None,
            "quantity": 2,
            "lot_code": "",
            "expires_on": None,
            "lot_status": "",
            "storage_conditions": "",
        }

        line_form_success = _FakeForm(valid=True, cleaned_data={**base_cleaned, "receive_now": False})
        with mock.patch("wms.receipt_handlers.resolve_product", return_value=product):
            with mock.patch("wms.receipt_handlers.messages.success"):
                response, lines, pending = handle_receipt_action(
                    self._request({"action": "add_line"}),
                    action="add_line",
                    select_form=_FakeForm(valid=False),
                    create_form=_FakeForm(valid=False),
                    line_form=line_form_success,
                    selected_receipt=selected_receipt,
                )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(lines)
        self.assertIsNone(pending)

        line_form_receive_now = _FakeForm(valid=True, cleaned_data={**base_cleaned, "receive_now": True})
        with mock.patch("wms.receipt_handlers.resolve_product", return_value=product):
            with mock.patch(
                "wms.receipt_handlers.receive_receipt_line",
                side_effect=StockError("Stock NOK"),
            ):
                with mock.patch(
                    "wms.receipt_handlers.get_receipt_lines_state",
                    return_value=(["line"], 1),
                ):
                    response, lines, pending = handle_receipt_action(
                        self._request({"action": "add_line"}),
                        action="add_line",
                        select_form=_FakeForm(valid=False),
                        create_form=_FakeForm(valid=False),
                        line_form=line_form_receive_now,
                        selected_receipt=selected_receipt,
                    )
        self.assertIsNone(response)
        self.assertEqual(lines, ["line"])
        self.assertEqual(pending, 1)
        self.assertIn((None, "Stock NOK"), line_form_receive_now.errors)

    def test_handle_receipt_action_add_line_receive_now_success(self):
        line_model = SimpleNamespace(quantity=3)
        selected_receipt = SimpleNamespace(
            id=11,
            status=ReceiptStatus.DRAFT,
            lines=SimpleNamespace(create=lambda **kwargs: line_model),
        )
        location = SimpleNamespace(id=2)
        product = SimpleNamespace(default_location=location, storage_conditions="Cold", name="Gloves")
        line_form = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "GLV",
                "location": None,
                "quantity": 3,
                "lot_code": "",
                "expires_on": None,
                "lot_status": "",
                "storage_conditions": "",
                "receive_now": True,
            },
        )
        with mock.patch("wms.receipt_handlers.resolve_product", return_value=product):
            with mock.patch("wms.receipt_handlers.receive_receipt_line") as receive_mock:
                with mock.patch("wms.receipt_handlers.messages.success") as success_mock:
                    response, lines, pending = handle_receipt_action(
                        self._request({"action": "add_line"}),
                        action="add_line",
                        select_form=_FakeForm(valid=False),
                        create_form=_FakeForm(valid=False),
                        line_form=line_form,
                        selected_receipt=selected_receipt,
                    )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        receive_mock.assert_called_once_with(user=self.user, line=line_model)
        success_mock.assert_called_once_with(
            mock.ANY,
            "Ligne réceptionnée: Gloves (3).",
        )

    def test_handle_receipt_action_receive_lines_processes_and_reports_errors(self):
        line_ok = SimpleNamespace(received_lot_id=None)
        line_skip = SimpleNamespace(received_lot_id=12)
        line_ko = SimpleNamespace(received_lot_id=None)
        selected_receipt = SimpleNamespace(
            id=8,
            lines=SimpleNamespace(select_related=lambda *args: [line_ok, line_skip, line_ko]),
        )
        with mock.patch(
            "wms.receipt_handlers.receive_receipt_line",
            side_effect=[None, StockError("Line error")],
        ):
            with mock.patch("wms.receipt_handlers.messages.success") as success_mock:
                with mock.patch("wms.receipt_handlers.messages.error") as error_mock:
                    response, lines, pending = handle_receipt_action(
                        self._request({"action": "receive_lines"}),
                        action="receive_lines",
                        select_form=_FakeForm(valid=False),
                        create_form=_FakeForm(valid=False),
                        line_form=_FakeForm(valid=False),
                        selected_receipt=selected_receipt,
                    )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
        success_mock.assert_called_once_with(mock.ANY, "1 ligne(s) réceptionnée(s).")
        error_mock.assert_called_once_with(mock.ANY, "Line error")

    def test_handle_receipt_action_returns_none_for_unhandled_action(self):
        response, lines, pending = handle_receipt_action(
            self._request({"action": "noop"}),
            action="noop",
            select_form=_FakeForm(valid=False),
            create_form=_FakeForm(valid=False),
            line_form=_FakeForm(valid=False),
            selected_receipt=None,
        )
        self.assertIsNone(response)
        self.assertIsNone(lines)
        self.assertIsNone(pending)
