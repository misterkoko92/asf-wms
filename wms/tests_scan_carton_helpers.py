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

    def test_resolve_carton_size_invalid_custom(self):
        size, errors = resolve_carton_size(
            carton_format_id="custom", default_format=None, data={}
        )
        self.assertIsNone(size)
        self.assertTrue(errors)

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
