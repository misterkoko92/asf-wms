from django.test import TestCase

from wms.models import (
    Carton,
    CartonFormat,
    CartonItem,
    CartonStatus,
    Location,
    Product,
    ProductLot,
    Shipment,
    Warehouse,
)
from wms.scan_carton_helpers import (
    build_available_cartons,
    build_carton_formats,
    get_carton_volume_cm3,
    resolve_carton_size,
)


class ScanCartonHelpersTests(TestCase):
    def test_build_available_cartons_filters_and_sums_weight(self):
        warehouse = Warehouse.objects.create(name="Main")
        location = Location.objects.create(
            warehouse=warehouse, zone="A", aisle="01", shelf="001"
        )
        product = Product.objects.create(name="Item", sku="SKU-1", weight_g=100)
        lot = ProductLot.objects.create(
            product=product,
            quantity_on_hand=5,
            location=location,
        )
        ready = Carton.objects.create(code="C-READY", status=CartonStatus.PACKED)
        CartonItem.objects.create(carton=ready, product_lot=lot, quantity=2)
        Carton.objects.create(code="C-OUT", status=CartonStatus.PICKING)
        shipment = Shipment.objects.create(
            shipper_name="Sender",
            recipient_name="Recipient",
            destination_address="10 Rue Test",
            destination_country="France",
        )
        assigned = Carton.objects.create(
            code="C-ASSIGNED",
            status=CartonStatus.PACKED,
            shipment=shipment,
        )
        CartonItem.objects.create(carton=assigned, product_lot=lot, quantity=1)

        options = build_available_cartons()
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["code"], "C-READY")
        self.assertEqual(options[0]["weight_g"], 200)

    def test_build_carton_formats_returns_default(self):
        fmt = CartonFormat.objects.create(
            name="Default",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        data, default_format = build_carton_formats()
        self.assertEqual(default_format.id, fmt.id)
        self.assertEqual(len(data), 1)

    def test_build_carton_formats_uses_first_when_no_default_flag(self):
        first = CartonFormat.objects.create(
            name="A-First",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=False,
        )
        CartonFormat.objects.create(
            name="B-Second",
            length_cm=50,
            width_cm=40,
            height_cm=40,
            max_weight_g=9000,
            is_default=False,
        )

        data, default_format = build_carton_formats()

        self.assertEqual(len(data), 2)
        self.assertEqual(default_format.id, first.id)

    def test_resolve_carton_size_from_format(self):
        fmt = CartonFormat.objects.create(
            name="Small",
            length_cm=10,
            width_cm=20,
            height_cm=30,
            max_weight_g=1000,
        )
        size, errors = resolve_carton_size(
            carton_format_id=str(fmt.id), default_format=None, data={}
        )
        self.assertEqual(errors, [])
        self.assertEqual(size["length_cm"], fmt.length_cm)
        self.assertEqual(size["max_weight_g"], fmt.max_weight_g)

    def test_resolve_carton_size_uses_default_format_when_id_missing(self):
        fmt = CartonFormat.objects.create(
            name="DefaultSize",
            length_cm=15,
            width_cm=25,
            height_cm=35,
            max_weight_g=1500,
        )

        size, errors = resolve_carton_size(
            carton_format_id="",
            default_format=fmt,
            data={},
        )

        self.assertEqual(errors, [])
        self.assertEqual(size["length_cm"], fmt.length_cm)
        self.assertEqual(size["max_weight_g"], fmt.max_weight_g)

    def test_resolve_carton_size_invalid_custom(self):
        size, errors = resolve_carton_size(
            carton_format_id="custom", default_format=None, data={}
        )
        self.assertIsNone(size)
        self.assertTrue(errors)

    def test_resolve_carton_size_invalid_non_numeric_format_id(self):
        size, errors = resolve_carton_size(
            carton_format_id="not-a-number",
            default_format=None,
            data={},
        )

        self.assertIsNone(size)
        self.assertEqual(errors, ["Format de carton invalide."])

    def test_resolve_carton_size_invalid_unknown_format_id(self):
        size, errors = resolve_carton_size(
            carton_format_id="99999",
            default_format=None,
            data={},
        )

        self.assertIsNone(size)
        self.assertEqual(errors, ["Format de carton invalide."])

    def test_resolve_carton_size_custom_valid(self):
        size, errors = resolve_carton_size(
            carton_format_id="custom",
            default_format=None,
            data={
                "carton_length_cm": "10",
                "carton_width_cm": "20",
                "carton_height_cm": "30",
                "carton_max_weight_g": "1000",
            },
        )
        self.assertEqual(errors, [])
        self.assertEqual(size["length_cm"], 10)
        self.assertEqual(size["max_weight_g"], 1000)

    def test_get_carton_volume_cm3_multiplies_dimensions(self):
        volume = get_carton_volume_cm3(
            {"length_cm": 10, "width_cm": 20, "height_cm": 30}
        )
        self.assertEqual(volume, 6000)
