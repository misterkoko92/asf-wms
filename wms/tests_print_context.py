from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.print_context import (
    _build_destination_info,
    build_carton_document_context,
    build_carton_picking_context,
    build_label_context,
    build_preview_context,
    build_product_label_context,
    build_product_qr_label_context,
    build_sample_document_context,
    build_sample_label_context,
    build_sample_product_label_context,
    build_sample_product_qr_label_context,
    build_shipment_document_context,
    resolve_rack_color,
)


class _FakeCartonSet:
    def __init__(self, cartons):
        self._cartons = cartons

    def all(self):
        return SimpleNamespace(order_by=lambda *_args: self._cartons)

    def first(self):
        return self._cartons[0] if self._cartons else None


class PrintContextTests(SimpleTestCase):
    def test_build_destination_info(self):
        shipment_with_destination = SimpleNamespace(
            destination=SimpleNamespace(city="Abidjan", iata_code="ABJ"),
            destination_address="unused",
        )
        self.assertEqual(
            _build_destination_info(shipment_with_destination),
            ("Abidjan", "ABJ", "Abidjan (ABJ)"),
        )

        shipment_without_destination = SimpleNamespace(
            destination=None,
            destination_address="Adresse fallback",
        )
        self.assertEqual(
            _build_destination_info(shipment_without_destination),
            ("", "", "Adresse fallback"),
        )

    def test_build_shipment_document_context_hides_measurements_when_missing_defaults(self):
        cartons = [SimpleNamespace(id=10), SimpleNamespace(id=11)]
        shipment = SimpleNamespace(
            reference="SHP-10",
            shipper_name="ASF",
            shipper_contact="Shipper Contact",
            recipient_name="Recipient",
            recipient_contact="Recipient Contact",
            correspondent_name="Correspondent",
            destination=SimpleNamespace(city="Paris", iata_code="CDG"),
            destination_address="Fallback Address",
            destination_country="France",
            requested_delivery_date=None,
            notes="",
            carton_set=_FakeCartonSet(cartons),
        )

        cart_rows = [
            {
                "weight_g": 1000,
                "volume_cm3": 500000,
                "length_cm": 40,
                "width_cm": 30,
                "height_cm": 20,
            },
            {
                "weight_g": 2000,
                "volume_cm3": 250000,
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
            },
        ]
        item = SimpleNamespace(
            carton_id=10,
            product_lot=SimpleNamespace(product=SimpleNamespace(id=1)),
        )
        carton_items_qs = mock.MagicMock()
        carton_items_qs.select_related.return_value = [item]

        with mock.patch("wms.print_context.build_shipment_item_rows", return_value=[{"product": "Mask"}]):
            with mock.patch("wms.print_context.build_shipment_aggregate_rows", return_value=[{"product": "Mask"}]):
                with mock.patch(
                    "wms.print_context.CartonFormat.objects.filter",
                    return_value=SimpleNamespace(first=lambda: None),
                ):
                    with mock.patch("wms.print_context.CartonFormat.objects.first", return_value=SimpleNamespace(id=1)):
                        with mock.patch("wms.print_context.build_carton_rows", return_value=cart_rows):
                            with mock.patch(
                                "wms.print_context.CartonItem.objects.filter",
                                return_value=carton_items_qs,
                            ):
                                with mock.patch("wms.print_context.get_product_weight_g", return_value=None):
                                    with mock.patch("wms.print_context.get_product_volume_cm3", return_value=None):
                                        with mock.patch("wms.print_context.compute_weight_total_g", return_value=3000):
                                            with mock.patch("wms.print_context.build_shipment_type_labels", return_value="TypeX"):
                                                with mock.patch(
                                                    "wms.print_context.build_contact_info",
                                                    side_effect=lambda tag, name: {"tag": tag, "name": name},
                                                ):
                                                    with mock.patch(
                                                        "wms.print_context.build_org_context",
                                                        return_value={"org": "ASF"},
                                                    ):
                                                        context = build_shipment_document_context(
                                                            shipment,
                                                            "packing_list_shipment",
                                                        )

        self.assertEqual(context["org"], "ASF")
        self.assertEqual(context["shipment_ref"], "SHP-10")
        self.assertTrue(context["hide_footer"])
        self.assertTrue(context["show_carton_column"])
        self.assertEqual(context["destination_label"], "Paris (CDG)")
        self.assertEqual(context["donation_description"], "2 cartons, 1 produits")
        self.assertIsNone(context["weight_total_kg"])
        self.assertIsNone(context["volume_total_m3"])
        self.assertIsNone(context["carton_rows"][0]["weight_kg"])
        self.assertIsNone(context["carton_rows"][0]["volume_m3"])
        self.assertEqual(context["carton_rows"][0]["dimensions_cm"], "40 x 30 x 20")
        self.assertIsNone(context["carton_rows"][1]["dimensions_cm"])

    def test_build_shipment_document_context_regular_measurements_and_description(self):
        cartons = [SimpleNamespace(id=30)]
        shipment = SimpleNamespace(
            reference="SHP-30",
            shipper_name="ASF",
            shipper_contact="",
            recipient_name="Hospital",
            recipient_contact="",
            correspondent_name="Corr",
            destination=None,
            destination_address="Abidjan Airport",
            destination_country="COTE D'IVOIRE",
            requested_delivery_date=date(2026, 1, 15),
            notes="Specific note",
            carton_set=_FakeCartonSet(cartons),
        )
        cart_rows = [
            {
                "weight_g": 1500,
                "volume_cm3": 200000,
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
            }
        ]
        carton_items_qs = mock.MagicMock()
        carton_items_qs.select_related.return_value = []

        with mock.patch("wms.print_context.build_shipment_item_rows", return_value=[]):
            with mock.patch("wms.print_context.build_shipment_aggregate_rows", return_value=[{"product": "Mask"}]):
                with mock.patch(
                    "wms.print_context.CartonFormat.objects.filter",
                    return_value=SimpleNamespace(first=lambda: SimpleNamespace(id=9)),
                ):
                    with mock.patch("wms.print_context.build_carton_rows", return_value=cart_rows):
                        with mock.patch(
                            "wms.print_context.CartonItem.objects.filter",
                            return_value=carton_items_qs,
                        ):
                            with mock.patch("wms.print_context.compute_weight_total_g", return_value=1500):
                                with mock.patch("wms.print_context.build_shipment_type_labels", return_value="TypeY"):
                                    with mock.patch("wms.print_context.build_contact_info", return_value={"x": "y"}):
                                        with mock.patch(
                                            "wms.print_context.build_org_context",
                                            return_value={"org": "ASF"},
                                        ):
                                            context = build_shipment_document_context(shipment, "shipment_note")

        self.assertFalse(context["hide_footer"])
        self.assertFalse(context["show_carton_column"])
        self.assertEqual(context["destination_label"], "Abidjan Airport")
        self.assertEqual(context["weight_total_kg"], 1.5)
        self.assertEqual(context["volume_total_m3"], 0.2)
        self.assertEqual(context["carton_rows"][0]["weight_kg"], 1.5)
        self.assertEqual(context["carton_rows"][0]["volume_m3"], 0.2)
        self.assertIsNone(context["carton_rows"][0]["dimensions_cm"])
        self.assertEqual(context["donation_description"], "Specific note")
        self.assertIn("livraison souhaitee 15/01/2026", context["shipment_description"])

    def test_build_carton_document_context_handles_missing_defaults_and_weight(self):
        shipment = SimpleNamespace(reference="SHP-40")
        product_ok = SimpleNamespace(name="Mask", weight_g=400)
        product_missing = SimpleNamespace(name="Unknown", weight_g=None)
        item_ok = SimpleNamespace(
            quantity=2,
            product_lot=SimpleNamespace(product=product_ok, lot_code="LOT-1", expires_on=None),
        )
        item_missing = SimpleNamespace(
            quantity=1,
            product_lot=SimpleNamespace(product=product_missing, lot_code="", expires_on=None),
        )
        carton = SimpleNamespace(
            code="C-40",
            cartonitem_set=SimpleNamespace(select_related=lambda *_args: [item_ok, item_missing]),
        )

        with mock.patch(
            "wms.print_context.get_product_weight_g",
            side_effect=[100, None],
        ):
            with mock.patch(
                "wms.print_context.get_product_volume_cm3",
                return_value=None,
            ):
                context = build_carton_document_context(shipment, carton)

        self.assertEqual(context["carton_code"], "C-40")
        self.assertEqual(len(context["item_rows"]), 2)
        self.assertIsNone(context["carton_weight_kg"])
        self.assertTrue(context["hide_footer"])

    def test_build_carton_picking_context_groups_and_sorts(self):
        product = SimpleNamespace(id=1, name="Mask", brand="Brand")
        location = SimpleNamespace(id=10, zone="Z1", aisle="A1", shelf="S1")
        lot_a = SimpleNamespace(product=product, location=location, lot_code="L1")
        lot_b = SimpleNamespace(product=product, location=None, lot_code="L1")
        item_a = SimpleNamespace(product_lot=lot_a, quantity=2)
        item_b = SimpleNamespace(product_lot=lot_a, quantity=3)
        item_c = SimpleNamespace(product_lot=lot_b, quantity=1)
        carton = SimpleNamespace(
            code="C-50",
            cartonitem_set=SimpleNamespace(
                select_related=lambda *_args: [item_a, item_b, item_c]
            ),
        )

        with mock.patch(
            "wms.print_context.build_product_group_key",
            side_effect=lambda _p, _lot: ("group", "L1"),
        ):
            with mock.patch(
                "wms.print_context.build_product_label",
                return_value="Mask - Lot L1",
            ):
                context = build_carton_picking_context(carton)

        self.assertEqual(context["carton_code"], "C-50")
        self.assertTrue(context["hide_footer"])
        self.assertEqual(len(context["item_rows"]), 2)
        self.assertEqual(context["item_rows"][0]["location"], "-")
        self.assertEqual(context["item_rows"][0]["quantity"], 1)
        self.assertEqual(context["item_rows"][1]["location"], "Z1 - A1 - S1")
        self.assertEqual(context["item_rows"][1]["quantity"], 5)

    def test_build_label_context(self):
        shipment = SimpleNamespace(
            reference="SHP-60",
            destination=SimpleNamespace(city="abidjan", iata_code="abj"),
            destination_address="ignored",
            qr_code_image=SimpleNamespace(url="/media/qr.png"),
        )
        context = build_label_context(shipment, position=2, total=8)
        self.assertEqual(context["label_city"], "ABIDJAN")
        self.assertEqual(context["label_iata"], "ABJ")
        self.assertEqual(context["label_qr_url"], "/media/qr.png")
        self.assertEqual(context["label_position"], 2)
        self.assertEqual(context["label_total"], 8)

        shipment_no_destination = SimpleNamespace(
            reference="SHP-61",
            destination=None,
            destination_address="Bamako Hub",
            qr_code_image=None,
        )
        context_no_destination = build_label_context(shipment_no_destination, position=1, total=1)
        self.assertEqual(context_no_destination["label_city"], "BAMAKO HUB")
        self.assertEqual(context_no_destination["label_iata"], "")
        self.assertEqual(context_no_destination["label_qr_url"], "")

    def test_resolve_rack_color_and_product_label_context(self):
        self.assertIsNone(resolve_rack_color(None))

        location = SimpleNamespace(warehouse=SimpleNamespace(id=1), zone="A1", aisle="B1", shelf="C1")
        product = SimpleNamespace(
            name="Mask",
            brand="BrandX",
            color="Blue",
            photo=SimpleNamespace(url="/media/p.jpg"),
            default_location=location,
        )
        with mock.patch(
            "wms.print_context.RackColor.objects.filter",
            return_value=SimpleNamespace(first=lambda: SimpleNamespace(color="Green")),
        ):
            self.assertEqual(resolve_rack_color(location), "Green")

        with mock.patch(
            "wms.print_context.RackColor.objects.filter",
            return_value=SimpleNamespace(first=lambda: None),
        ):
            self.assertIsNone(resolve_rack_color(location))

        with mock.patch("wms.print_context.resolve_rack_color", return_value="Green") as resolver_mock:
            context = build_product_label_context(product)
        resolver_mock.assert_called_once_with(location)
        self.assertEqual(context["rack_color"], "Green")
        self.assertEqual(context["product_rack"], "A1")
        self.assertEqual(context["product_photo_url"], "/media/p.jpg")

        with mock.patch("wms.print_context.resolve_rack_color") as resolver_mock:
            explicit_context = build_product_label_context(product, rack_color="Red")
        resolver_mock.assert_not_called()
        self.assertEqual(explicit_context["rack_color"], "Red")

    def test_build_product_qr_and_sample_context_builders(self):
        product = SimpleNamespace(
            name="Mask",
            brand="BrandX",
            qr_code_image=SimpleNamespace(url="/media/qr-mask.png"),
        )
        qr_context = build_product_qr_label_context(product)
        self.assertEqual(qr_context["product_qr_url"], "/media/qr-mask.png")

        sample_label = build_sample_label_context()
        self.assertEqual(sample_label["label_city"], "BAMAKO")
        sample_product_label = build_sample_product_label_context()
        self.assertEqual(sample_product_label["rack_color"], "#1C8BC0")
        sample_product_qr = build_sample_product_qr_label_context()
        self.assertEqual(sample_product_qr["product_qr_url"], "")

        sample_doc = build_sample_document_context("packing_list_carton")
        self.assertTrue(sample_doc["hide_footer"])
        self.assertFalse(sample_doc["show_carton_column"])
        self.assertEqual(sample_doc["shipment_ref"], "YY0001")
        self.assertEqual(len(sample_doc["carton_rows"]), 2)

    def test_build_preview_context_routes_to_expected_builder(self):
        shipment = SimpleNamespace(
            carton_set=_FakeCartonSet([SimpleNamespace(code="C-1")]),
        )
        product = SimpleNamespace(id=1)

        with mock.patch("wms.print_context.build_label_context", return_value={"k": "v"}) as label_mock:
            result = build_preview_context("shipment_label", shipment=shipment)
        label_mock.assert_called_once_with(shipment, position=1, total=10)
        self.assertEqual(result, {"k": "v"})

        with mock.patch("wms.print_context.build_sample_label_context", return_value={"sample": 1}) as sample_label_mock:
            result = build_preview_context("shipment_label")
        sample_label_mock.assert_called_once()
        self.assertEqual(result, {"sample": 1})

        with mock.patch("wms.print_context.build_product_label_context", return_value={"pl": 1}) as product_label_mock:
            result = build_preview_context("product_label", product=product)
        product_label_mock.assert_called_once_with(product)
        self.assertEqual(result, {"pl": 1})

        with mock.patch("wms.print_context.build_sample_product_label_context", return_value={"spl": 1}) as sample_product_label_mock:
            result = build_preview_context("product_label")
        sample_product_label_mock.assert_called_once()
        self.assertEqual(result, {"spl": 1})

        with mock.patch("wms.print_context.build_product_qr_label_context", return_value={"pq": 1}) as product_qr_mock:
            result = build_preview_context("product_qr", product=product)
        product_qr_mock.assert_called_once_with(product)
        self.assertEqual(result, {"pq": 1})

        with mock.patch("wms.print_context.build_sample_product_qr_label_context", return_value={"spq": 1}) as sample_product_qr_mock:
            result = build_preview_context("product_qr")
        sample_product_qr_mock.assert_called_once()
        self.assertEqual(result, {"spq": 1})

        with mock.patch("wms.print_context.build_carton_document_context", return_value={"carton": 1}) as carton_doc_mock:
            result = build_preview_context("packing_list_carton", shipment=shipment)
        carton_doc_mock.assert_called_once()
        self.assertEqual(result, {"carton": 1})

        with mock.patch("wms.print_context.build_shipment_document_context", return_value={"ship": 1}) as ship_doc_mock:
            result = build_preview_context("shipment_note", shipment=shipment)
        ship_doc_mock.assert_called_once_with(shipment, "shipment_note")
        self.assertEqual(result, {"ship": 1})

        with mock.patch("wms.print_context.build_sample_document_context", return_value={"sample_doc": 1}) as sample_doc_mock:
            result = build_preview_context("shipment_note")
        sample_doc_mock.assert_called_once_with("shipment_note")
        self.assertEqual(result, {"sample_doc": 1})
