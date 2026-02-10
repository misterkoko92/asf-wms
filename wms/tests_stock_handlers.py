from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from wms.stock_out_handlers import handle_stock_out_post
from wms.stock_update_handlers import handle_stock_update_post
from wms.services import StockError


class _FakeForm:
    def __init__(self, *, valid, cleaned_data=None, product=None):
        self._valid = valid
        self.cleaned_data = cleaned_data or {}
        self.product = product
        self.errors = []

    def is_valid(self):
        return self._valid

    def add_error(self, field, error):
        self.errors.append((field, str(error)))


class StockHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, username="stock-user")

    def _request(self, data=None):
        request = self.factory.post("/scan/stock/", data or {})
        request.user = self.user
        return request

    def test_handle_stock_out_post_returns_none_when_form_invalid(self):
        form = _FakeForm(valid=False)
        self.assertIsNone(handle_stock_out_post(self._request(), form=form))

    def test_handle_stock_out_post_adds_error_when_product_not_found(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "UNKNOWN",
                "shipment_reference": "",
                "quantity": 1,
                "reason_code": "",
                "reason_notes": "",
            },
        )
        with mock.patch("wms.stock_out_handlers.resolve_product", return_value=None):
            response = handle_stock_out_post(self._request(), form=form)
        self.assertIsNone(response)
        self.assertIn(("product_code", "Produit introuvable."), form.errors)

    def test_handle_stock_out_post_adds_error_when_shipment_not_found(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "SKU-1",
                "shipment_reference": "S-404",
                "quantity": 1,
                "reason_code": "",
                "reason_notes": "",
            },
        )
        with mock.patch(
            "wms.stock_out_handlers.resolve_product",
            return_value=SimpleNamespace(name="Produit"),
        ):
            with mock.patch("wms.stock_out_handlers.resolve_shipment", return_value=None):
                response = handle_stock_out_post(self._request(), form=form)
        self.assertIsNone(response)
        self.assertIn(("shipment_reference", "Expedition introuvable."), form.errors)

    def test_handle_stock_out_post_success(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "SKU-1",
                "shipment_reference": "",
                "quantity": 3,
                "reason_code": "",
                "reason_notes": "",
            },
        )
        product = SimpleNamespace(name="Produit A")
        with mock.patch("wms.stock_out_handlers.resolve_product", return_value=product):
            with mock.patch("wms.stock_out_handlers.resolve_shipment", return_value=None):
                with mock.patch("wms.stock_out_handlers.consume_stock") as consume_mock:
                    with mock.patch("wms.stock_out_handlers.messages.success") as success_mock:
                        with mock.patch(
                            "wms.stock_out_handlers.redirect",
                            return_value=SimpleNamespace(status_code=302, url="/scan/out/"),
                        ) as redirect_mock:
                            response = handle_stock_out_post(self._request(), form=form)
        self.assertEqual(response.status_code, 302)
        consume_mock.assert_called_once()
        success_mock.assert_called_once()
        redirect_mock.assert_called_once_with("scan:scan_out")

    def test_handle_stock_out_post_adds_form_error_on_stock_exception(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "product_code": "SKU-1",
                "shipment_reference": "",
                "quantity": 1,
                "reason_code": "",
                "reason_notes": "",
            },
        )
        with mock.patch(
            "wms.stock_out_handlers.resolve_product",
            return_value=SimpleNamespace(name="Produit"),
        ):
            with mock.patch("wms.stock_out_handlers.resolve_shipment", return_value=None):
                with mock.patch(
                    "wms.stock_out_handlers.consume_stock",
                    side_effect=StockError("boom"),
                ):
                    response = handle_stock_out_post(self._request(), form=form)
        self.assertIsNone(response)
        self.assertIn((None, "boom"), form.errors)

    def test_handle_stock_update_post_returns_none_when_form_invalid(self):
        form = _FakeForm(valid=False)
        self.assertIsNone(handle_stock_update_post(self._request(), form=form))

    def test_handle_stock_update_post_requires_product_location(self):
        form = _FakeForm(
            valid=True,
            cleaned_data={"quantity": 1},
            product=SimpleNamespace(default_location=None),
        )
        response = handle_stock_update_post(self._request(), form=form)
        self.assertIsNone(response)
        self.assertIn((None, "Emplacement requis pour ce produit."), form.errors)

    def test_handle_stock_update_post_success_without_donor(self):
        warehouse = SimpleNamespace(id=1)
        location = SimpleNamespace(warehouse=warehouse)
        product = SimpleNamespace(default_location=location)
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "quantity": 4,
                "lot_code": "LOT-1",
                "expires_on": None,
                "donor_contact": None,
            },
            product=product,
        )
        with mock.patch("wms.stock_update_handlers.receive_stock") as receive_mock:
            with mock.patch("wms.stock_update_handlers.messages.success") as success_mock:
                with mock.patch(
                    "wms.stock_update_handlers.redirect",
                    return_value=SimpleNamespace(status_code=302, url="/scan/stock-update/"),
                ) as redirect_mock:
                    response = handle_stock_update_post(self._request(), form=form)
        self.assertEqual(response.status_code, 302)
        receive_mock.assert_called_once()
        self.assertIsNone(receive_mock.call_args.kwargs["source_receipt"])
        success_mock.assert_called_once_with(mock.ANY, "Stock mis a jour.")
        redirect_mock.assert_called_once_with("scan:scan_stock_update")

    def test_handle_stock_update_post_creates_receipt_when_donor_present(self):
        warehouse = SimpleNamespace(id=1)
        location = SimpleNamespace(warehouse=warehouse)
        donor = SimpleNamespace(id=7)
        product = SimpleNamespace(default_location=location)
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "quantity": 2,
                "lot_code": "",
                "expires_on": None,
                "donor_contact": donor,
            },
            product=product,
        )
        created_receipt = SimpleNamespace(id=11)
        with mock.patch(
            "wms.stock_update_handlers.Receipt.objects.create",
            return_value=created_receipt,
        ) as create_receipt_mock:
            with mock.patch("wms.stock_update_handlers.receive_stock") as receive_mock:
                with mock.patch("wms.stock_update_handlers.messages.success"):
                    with mock.patch(
                        "wms.stock_update_handlers.redirect",
                        return_value=SimpleNamespace(status_code=302, url="/scan/stock-update/"),
                    ):
                        response = handle_stock_update_post(self._request(), form=form)
        self.assertEqual(response.status_code, 302)
        create_receipt_mock.assert_called_once()
        self.assertEqual(receive_mock.call_args.kwargs["source_receipt"], created_receipt)

    def test_handle_stock_update_post_adds_error_on_stock_exception(self):
        warehouse = SimpleNamespace(id=1)
        location = SimpleNamespace(warehouse=warehouse)
        product = SimpleNamespace(default_location=location)
        form = _FakeForm(
            valid=True,
            cleaned_data={
                "quantity": 1,
                "lot_code": "",
                "expires_on": None,
                "donor_contact": None,
            },
            product=product,
        )
        with mock.patch(
            "wms.stock_update_handlers.receive_stock",
            side_effect=StockError("stock issue"),
        ):
            response = handle_stock_update_post(self._request(), form=form)
        self.assertIsNone(response)
        self.assertIn((None, "stock issue"), form.errors)
