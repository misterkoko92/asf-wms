from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, TestCase

from wms.pack_handlers import build_pack_defaults, handle_pack_post
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


class PackHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=31, username="packer")

    def _request(self, data=None):
        request = self.factory.post("/scan/pack/", data or {})
        request.user = self.user
        request.session = {}
        return request

    def _form(self, *, valid=True, shipment_reference="", current_location=None):
        return _FakeForm(
            valid=valid,
            cleaned_data={
                "shipment_reference": shipment_reference,
                "current_location": current_location,
            },
        )

    def _carton_size(self):
        return {
            "length_cm": Decimal("40"),
            "width_cm": Decimal("30"),
            "height_cm": Decimal("30"),
            "max_weight_g": 8000,
        }

    def test_build_pack_defaults_with_and_without_default_format(self):
        default_format = SimpleNamespace(
            id=9,
            length_cm=Decimal("60"),
            width_cm=Decimal("40"),
            height_cm=Decimal("35"),
            max_weight_g=12000,
        )
        format_id, custom, line_count, line_values = build_pack_defaults(default_format)
        self.assertEqual(format_id, "9")
        self.assertEqual(
            custom,
            {
                "length_cm": Decimal("60"),
                "width_cm": Decimal("40"),
                "height_cm": Decimal("35"),
                "max_weight_g": 12000,
            },
        )
        self.assertEqual(line_count, 1)
        self.assertEqual(line_values, [{"product_code": "", "quantity": ""}])

        format_id, custom, line_count, line_values = build_pack_defaults(None)
        self.assertEqual(format_id, "custom")
        self.assertEqual(
            custom,
            {
                "length_cm": Decimal("40"),
                "width_cm": Decimal("30"),
                "height_cm": Decimal("30"),
                "max_weight_g": 8000,
            },
        )
        self.assertEqual(line_count, 1)
        self.assertEqual(line_values, [{"product_code": "", "quantity": ""}])

    def test_handle_pack_post_validates_shipment_carton_and_line_fields(self):
        request = self._request(
            {
                "line_count": "4",
                "line_2_quantity": "2",
                "line_3_product_code": "SKU-3",
                "line_4_product_code": "BAD",
                "line_4_quantity": "-1",
            }
        )
        form = self._form(valid=True, shipment_reference="SHIP-404")
        with mock.patch("wms.pack_handlers.resolve_shipment", return_value=None):
            with mock.patch(
                "wms.pack_handlers.resolve_carton_size",
                return_value=(self._carton_size(), ["Format invalide."]),
            ):
                with mock.patch(
                    "wms.pack_handlers.resolve_product",
                    side_effect=[SimpleNamespace(name="Good"), None],
                ):
                    response, state = handle_pack_post(
                        request,
                        form=form,
                        default_format=None,
                    )

        self.assertIsNone(response)
        self.assertIn(("shipment_reference", "Expédition introuvable."), form.errors)
        self.assertIn((None, "Format invalide."), form.errors)
        self.assertEqual(state["line_count"], 4)
        self.assertEqual(state["line_errors"]["2"], ["Produit requis."])
        self.assertEqual(state["line_errors"]["3"], ["Quantité requise."])
        self.assertIn("Quantité invalide.", state["line_errors"]["4"])
        self.assertIn("Produit introuvable.", state["line_errors"]["4"])

    def test_handle_pack_post_requires_at_least_one_product(self):
        request = self._request({"line_count": "1"})
        form = self._form(valid=True, shipment_reference="")
        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            response, state = handle_pack_post(
                request,
                form=form,
                default_format=None,
            )
        self.assertIsNone(response)
        self.assertEqual(state["line_errors"], {})
        self.assertIn((None, "Ajoutez au moins un produit."), form.errors)

    def test_handle_pack_post_warns_when_missing_defaults_without_confirmation(self):
        request = self._request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-1",
                "line_1_quantity": "2",
            }
        )
        product = SimpleNamespace(name="Masque")
        form = self._form(valid=True, shipment_reference="")
        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.resolve_product", return_value=product):
                with mock.patch("wms.pack_handlers.get_product_weight_g", return_value=None):
                    with mock.patch("wms.pack_handlers.get_product_volume_cm3", return_value=None):
                        response, state = handle_pack_post(
                            request,
                            form=form,
                            default_format=None,
                        )

        self.assertIsNone(response)
        self.assertEqual(state["missing_defaults"], ["Masque"])
        self.assertFalse(state["confirm_defaults"])
        self.assertTrue(form.errors)
        self.assertIn("Masque", form.errors[0][1])

    def test_handle_pack_post_adds_errors_when_bin_packing_fails(self):
        request = self._request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-1",
                "line_1_quantity": "1",
            }
        )
        product = SimpleNamespace(name="Produit 1")
        form = self._form(valid=True, shipment_reference="")
        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.resolve_product", return_value=product):
                with mock.patch("wms.pack_handlers.get_product_weight_g", return_value=20):
                    with mock.patch("wms.pack_handlers.get_product_volume_cm3", return_value=30):
                        with mock.patch(
                            "wms.pack_handlers.build_packing_bins",
                            return_value=(None, ["Impossible de preparer."], []),
                        ):
                            response, _state = handle_pack_post(
                                request,
                                form=form,
                                default_format=None,
                            )

        self.assertIsNone(response)
        self.assertIn((None, "Impossible de preparer."), form.errors)

    def test_handle_pack_post_success_with_warnings_sets_pack_results(self):
        request = self._request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-1",
                "line_1_quantity": "2",
                "confirm_defaults": "1",
            }
        )
        product = SimpleNamespace(id=5, name="Produit 1")
        created_carton = SimpleNamespace(id=77)
        form = self._form(valid=True, shipment_reference="")
        bins = [{"items": {product.id: {"product": product, "quantity": 2}}}]
        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.resolve_product", return_value=product):
                with mock.patch("wms.pack_handlers.get_product_weight_g", return_value=20):
                    with mock.patch("wms.pack_handlers.get_product_volume_cm3", return_value=30):
                        with mock.patch(
                            "wms.pack_handlers.build_packing_bins",
                            return_value=(bins, [], ["Avertissement"]),
                        ):
                            with mock.patch(
                                "wms.pack_handlers.pack_carton",
                                return_value=created_carton,
                            ):
                                with mock.patch(
                                    "wms.pack_handlers.messages.warning"
                                ) as warning_mock:
                                    with mock.patch(
                                        "wms.pack_handlers.messages.success"
                                    ) as success_mock:
                                        response, state = handle_pack_post(
                                            request,
                                            form=form,
                                            default_format=None,
                                        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.session["pack_results"], [77])
        self.assertEqual(state["line_errors"], {})
        warning_mock.assert_called_once_with(request, "Avertissement")
        success_mock.assert_called_once_with(request, "1 carton(s) préparé(s).")

    def test_handle_pack_post_catches_stock_error(self):
        request = self._request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-1",
                "line_1_quantity": "1",
                "confirm_defaults": "1",
            }
        )
        product = SimpleNamespace(id=5, name="Produit 1")
        form = self._form(valid=True, shipment_reference="")
        bins = [{"items": {product.id: {"product": product, "quantity": 1}}}]
        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.resolve_product", return_value=product):
                with mock.patch("wms.pack_handlers.get_product_weight_g", return_value=20):
                    with mock.patch("wms.pack_handlers.get_product_volume_cm3", return_value=30):
                        with mock.patch(
                            "wms.pack_handlers.build_packing_bins",
                            return_value=(bins, [], []),
                        ):
                            with mock.patch(
                                "wms.pack_handlers.pack_carton",
                                side_effect=StockError("Stock insuffisant"),
                            ):
                                response, state = handle_pack_post(
                                    request,
                                    form=form,
                                    default_format=None,
                                )

        self.assertIsNone(response)
        self.assertEqual(state["line_errors"], {})
        self.assertIn((None, "Stock insuffisant"), form.errors)
