from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase

from wms.models import (
    Carton,
    CartonStatus,
    CartonStatusEvent,
    Location,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    Warehouse,
)
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
        self.staff_user = get_user_model().objects.create_user(
            username="pack-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )

    def _request(self, data=None):
        request = self.factory.post("/scan/pack/", data or {})
        request.user = self.user
        request.session = {}
        return request

    def _db_request(self, data=None, *, preparateur=False):
        request = self.factory.post("/scan/pack/", data or {})
        user = self.staff_user
        if preparateur:
            group, _ = Group.objects.get_or_create(name="Preparateur")
            user.groups.add(group)
        request.user = user
        request.session = {}
        return request

    def _form(
        self,
        *,
        valid=True,
        shipment_reference="",
        current_location=None,
        preassigned_destination=None,
    ):
        return _FakeForm(
            valid=valid,
            cleaned_data={
                "shipment_reference": shipment_reference,
                "current_location": current_location,
                "preassigned_destination": preassigned_destination,
            },
        )

    def _carton_size(self):
        return {
            "length_cm": Decimal("40"),
            "width_cm": Decimal("30"),
            "height_cm": Decimal("30"),
            "max_weight_g": 8000,
        }

    def _create_locations(self):
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        stock_location = Location.objects.create(
            warehouse=warehouse,
            zone="STOCK",
            aisle="01",
            shelf="001",
        )
        ready_mm = Location.objects.create(
            warehouse=warehouse,
            zone="READYMM",
            aisle="01",
            shelf="001",
            notes="Colis Prets MM",
        )
        ready_cn = Location.objects.create(
            warehouse=warehouse,
            zone="READYCN",
            aisle="01",
            shelf="001",
            notes="Colis Prets CN",
        )
        return stock_location, ready_mm, ready_cn

    def _create_stock_product(self, *, sku, name, category):
        stock_location, _, _ = self._create_locations()
        product = Product.objects.create(
            sku=sku,
            name=name,
            category=category,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-{sku}",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        return product

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
        self.assertEqual(
            line_values,
            [
                {
                    "product_code": "",
                    "quantity": "",
                    "expires_on": "",
                    "pack_family_override": "",
                }
            ],
        )

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
        self.assertEqual(
            line_values,
            [
                {
                    "product_code": "",
                    "quantity": "",
                    "expires_on": "",
                    "pack_family_override": "",
                }
            ],
        )

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

    def test_handle_pack_post_preparateur_splits_mm_and_cn_and_marks_cartons_available(self):
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        stock_location = Location.objects.create(
            warehouse=warehouse,
            zone="STOCK",
            aisle="01",
            shelf="001",
        )
        ready_mm = Location.objects.create(
            warehouse=warehouse,
            zone="READYMM",
            aisle="01",
            shelf="001",
            notes="Colis Prets MM",
        )
        ready_cn = Location.objects.create(
            warehouse=warehouse,
            zone="READYCN",
            aisle="01",
            shelf="001",
            notes="Colis Prets CN",
        )
        category_mm = ProductCategory.objects.create(name="MM")
        category_cn = ProductCategory.objects.create(name="CN")
        product_mm = Product.objects.create(
            sku="SKU-MM",
            name="Produit MM",
            category=category_mm,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        product_cn = Product.objects.create(
            sku="SKU-CN",
            name="Produit CN",
            category=category_cn,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product_mm,
            lot_code="LOT-MM",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        ProductLot.objects.create(
            product=product_cn,
            lot_code="LOT-CN",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        request = self._db_request(
            {
                "line_count": "2",
                "line_1_product_code": "SKU-MM",
                "line_1_quantity": "2",
                "line_2_product_code": "SKU-CN",
                "line_2_quantity": "3",
            },
            preparateur=True,
        )
        form = self._form(valid=True, shipment_reference="")

        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.messages.warning") as warning_mock:
                with mock.patch("wms.pack_handlers.messages.success") as success_mock:
                    response, state = handle_pack_post(
                        request,
                        form=form,
                        default_format=None,
                    )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(state["line_errors"], {})
        self.assertEqual(Carton.objects.count(), 2)
        self.assertEqual(
            list(Carton.objects.values_list("status", flat=True)),
            [CartonStatus.PACKED, CartonStatus.PACKED],
        )
        self.assertEqual(
            set(Carton.objects.values_list("current_location_id", flat=True)),
            {ready_mm.id, ready_cn.id},
        )
        self.assertEqual(
            set(code.split("-")[0] for code in Carton.objects.values_list("code", flat=True)),
            {"MM", "CN"},
        )
        self.assertEqual(
            request.session["pack_results"],
            [
                {"carton_id": mock.ANY, "zone_label": "Colis Prets MM", "family": "MM"},
                {"carton_id": mock.ANY, "zone_label": "Colis Prets CN", "family": "CN"},
            ],
        )
        warning_mock.assert_not_called()
        success_mock.assert_called_once_with(request, "2 carton(s) préparé(s).")

    def test_handle_pack_post_prepare_available_sets_ready_location_for_single_family(self):
        stock_location, ready_mm, _ready_cn = self._create_locations()
        category_mm = ProductCategory.objects.create(name="MM")
        product_mm = Product.objects.create(
            sku="SKU-MM-READY",
            name="Produit MM Ready",
            category=category_mm,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product_mm,
            lot_code="LOT-MM-READY",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        request = self._db_request(
            {
                "action": "prepare_available",
                "line_count": "1",
                "line_1_product_code": "SKU-MM-READY",
                "line_1_quantity": "2",
            }
        )
        form = self._form(valid=True, shipment_reference="")

        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.messages.warning") as warning_mock:
                with mock.patch("wms.pack_handlers.messages.success"):
                    response, state = handle_pack_post(
                        request,
                        form=form,
                        default_format=None,
                    )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(state["line_errors"], {})
        carton = Carton.objects.get()
        self.assertEqual(carton.status, CartonStatus.PACKED)
        self.assertEqual(carton.current_location, ready_mm)
        self.assertFalse(
            CartonStatusEvent.objects.filter(
                carton=carton,
                new_status=CartonStatus.PICKING,
            ).exists()
        )
        warning_mock.assert_not_called()

    def test_handle_pack_post_prepare_available_leaves_location_empty_for_mixed_families(self):
        stock_location, _ready_mm, _ready_cn = self._create_locations()
        category_mm = ProductCategory.objects.create(name="MM")
        category_cn = ProductCategory.objects.create(name="CN")
        product_mm = Product.objects.create(
            sku="SKU-MM-MIX",
            name="Produit MM Mix",
            category=category_mm,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        product_cn = Product.objects.create(
            sku="SKU-CN-MIX",
            name="Produit CN Mix",
            category=category_cn,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product_mm,
            lot_code="LOT-MM-MIX",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        ProductLot.objects.create(
            product=product_cn,
            lot_code="LOT-CN-MIX",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        request = self._db_request(
            {
                "action": "prepare_available",
                "line_count": "2",
                "line_1_product_code": "SKU-MM-MIX",
                "line_1_quantity": "1",
                "line_2_product_code": "SKU-CN-MIX",
                "line_2_quantity": "1",
            }
        )
        form = self._form(valid=True, shipment_reference="")

        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.messages.warning") as warning_mock:
                with mock.patch("wms.pack_handlers.messages.success"):
                    response, state = handle_pack_post(
                        request,
                        form=form,
                        default_format=None,
                    )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(state["line_errors"], {})
        carton = Carton.objects.get()
        self.assertEqual(carton.status, CartonStatus.PACKED)
        self.assertIsNone(carton.current_location)
        warning_mock.assert_called_once()
        self.assertIn("READY", warning_mock.call_args[0][1])

    def test_handle_pack_post_preparateur_requires_manual_mm_cn_override(self):
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        stock_location = Location.objects.create(
            warehouse=warehouse,
            zone="STOCK",
            aisle="01",
            shelf="001",
        )
        Location.objects.create(
            warehouse=warehouse,
            zone="READYMM",
            aisle="01",
            shelf="001",
            notes="Colis Prets MM",
        )
        Location.objects.create(
            warehouse=warehouse,
            zone="READYCN",
            aisle="01",
            shelf="001",
            notes="Colis Prets CN",
        )
        other_category = ProductCategory.objects.create(name="Autres")
        product = Product.objects.create(
            sku="SKU-OTHER",
            name="Produit autre",
            category=other_category,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-OTHER",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        request = self._db_request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-OTHER",
                "line_1_quantity": "1",
            },
            preparateur=True,
        )
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
        self.assertEqual(Carton.objects.count(), 0)
        self.assertIn("1", state["line_errors"])
        self.assertTrue(
            any("Choisissez manuellement MM ou CN" in error for error in state["line_errors"]["1"])
        )
        self.assertTrue(
            any("Choisissez manuellement MM ou CN" in error for _field, error in form.errors)
        )

    def test_handle_pack_post_preparateur_uses_manual_mm_cn_override_for_unknown_root(self):
        warehouse = Warehouse.objects.create(name="Main", code="MAIN")
        stock_location = Location.objects.create(
            warehouse=warehouse,
            zone="STOCK",
            aisle="01",
            shelf="001",
        )
        ready_mm = Location.objects.create(
            warehouse=warehouse,
            zone="READYMM",
            aisle="01",
            shelf="001",
            notes="Colis Prets MM",
        )
        Location.objects.create(
            warehouse=warehouse,
            zone="READYCN",
            aisle="01",
            shelf="001",
            notes="Colis Prets CN",
        )
        other_category = ProductCategory.objects.create(name="Autres")
        product = Product.objects.create(
            sku="SKU-OTHER",
            name="Produit autre",
            category=other_category,
            weight_g=100,
            length_cm=Decimal("10"),
            width_cm=Decimal("10"),
            height_cm=Decimal("10"),
            default_location=stock_location,
        )
        ProductLot.objects.create(
            product=product,
            lot_code="LOT-OTHER",
            status=ProductLotStatus.AVAILABLE,
            quantity_on_hand=20,
            location=stock_location,
        )
        request = self._db_request(
            {
                "line_count": "1",
                "line_1_product_code": "SKU-OTHER",
                "line_1_quantity": "1",
                "line_1_pack_family_override": "MM",
            },
            preparateur=True,
        )
        form = self._form(valid=True, shipment_reference="")

        with mock.patch(
            "wms.pack_handlers.resolve_carton_size",
            return_value=(self._carton_size(), []),
        ):
            with mock.patch("wms.pack_handlers.messages.warning"):
                with mock.patch("wms.pack_handlers.messages.success"):
                    response, state = handle_pack_post(
                        request,
                        form=form,
                        default_format=None,
                    )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(state["line_errors"], {})
        carton = Carton.objects.get()
        self.assertEqual(carton.status, CartonStatus.PACKED)
        self.assertEqual(carton.current_location, ready_mm)
        self.assertTrue(carton.code.startswith("MM-"))
