from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms import exports


class ExportsTests(SimpleTestCase):
    def test_bool_to_csv_and_build_csv_response(self):
        self.assertEqual(exports._bool_to_csv(True), "true")
        self.assertEqual(exports._bool_to_csv(False), "false")
        self.assertEqual(exports._bool_to_csv(None), "")

        response = exports._build_csv_response(
            "sample.csv",
            ["h1", "h2"],
            [["a", "b"]],
        )
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="sample.csv"')
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("\ufeff"))
        self.assertIn("h1;h2", content)
        self.assertIn("a;b", content)

    def test_export_products_csv_builds_expected_rows(self):
        location = SimpleNamespace(
            warehouse=SimpleNamespace(name="WH-A"),
            warehouse_id=1,
            zone="Z1",
            aisle="A1",
            shelf="S1",
        )
        category_root = SimpleNamespace(name="Cat1", parent=None)
        category_leaf = SimpleNamespace(name="Cat2", parent=category_root)
        product1 = SimpleNamespace(
            id=1,
            sku="SKU-1",
            name="Mask",
            brand="BrandX",
            color="Blue",
            category=category_leaf,
            tags=SimpleNamespace(all=lambda: [SimpleNamespace(name="Urgent"), SimpleNamespace(name="Medical")]),
            default_location=location,
            barcode="BC1",
            ean="EAN1",
            pu_ht="10",
            tva="20",
            pu_ttc="12",
            length_cm=10,
            width_cm=20,
            height_cm=30,
            weight_g=500,
            volume_cm3=6000,
            storage_conditions="Dry",
            perishable=True,
            quarantine_default=False,
            notes="n1",
            photo=SimpleNamespace(name="p1.jpg"),
        )
        product2 = SimpleNamespace(
            id=2,
            sku="SKU-2",
            name="Gloves",
            brand="",
            color="",
            category=None,
            tags=SimpleNamespace(all=lambda: []),
            default_location=None,
            barcode="",
            ean="",
            pu_ht="",
            tva="",
            pu_ttc="",
            length_cm=None,
            width_cm=None,
            height_cm=None,
            weight_g=None,
            volume_cm3=None,
            storage_conditions="",
            perishable=False,
            quarantine_default=True,
            notes="",
            photo=None,
        )

        stock_qs = mock.MagicMock()
        stock_values_qs = mock.MagicMock()
        stock_qs.values.return_value = stock_values_qs
        stock_values_qs.annotate.return_value = [
            {"product_id": 1, "total": 5},
            {"product_id": 2, "total": -3},
        ]
        product_qs = mock.MagicMock()
        product_qs.prefetch_related.return_value = product_qs
        product_qs.all.return_value = [product1, product2]

        with mock.patch(
            "wms.exports.RackColor.objects.all",
            return_value=[SimpleNamespace(warehouse_id=1, zone="Z1", color="Red")],
        ):
            with mock.patch("wms.exports.ProductLot.objects.filter", return_value=stock_qs):
                with mock.patch(
                    "wms.exports.Product.objects.select_related",
                    return_value=product_qs,
                ):
                    with mock.patch(
                        "wms.exports._build_csv_response",
                        return_value="products-response",
                    ) as response_mock:
                        result = exports.export_products_csv()

        self.assertEqual(result, "products-response")
        self.assertEqual(response_mock.call_args.args[0], "products_export.csv")
        rows = response_mock.call_args.args[2]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "SKU-1")
        self.assertEqual(rows[0][8], "Medical|Urgent")
        self.assertEqual(rows[0][13], "Red")
        self.assertEqual(rows[0][24], 5)
        self.assertEqual(rows[0][26], "true")
        self.assertEqual(rows[0][27], "false")
        self.assertEqual(rows[1][24], "")
        self.assertEqual(rows[1][26], "false")
        self.assertEqual(rows[1][27], "true")

    def test_export_locations_categories_and_warehouses_csv(self):
        locations_qs = mock.MagicMock()
        locations_qs.all.return_value = [
            SimpleNamespace(
                warehouse=SimpleNamespace(name="WH-A"),
                warehouse_id=1,
                zone="Z1",
                aisle="A1",
                shelf="S1",
                notes="n1",
            )
        ]
        with mock.patch(
            "wms.exports.RackColor.objects.all",
            return_value=[SimpleNamespace(warehouse_id=1, zone="Z1", color="Red")],
        ):
            with mock.patch(
                "wms.exports.Location.objects.select_related",
                return_value=locations_qs,
            ):
                with mock.patch(
                    "wms.exports._build_csv_response",
                    return_value="locations-response",
                ) as location_response_mock:
                    self.assertEqual(exports.export_locations_csv(), "locations-response")
        self.assertEqual(location_response_mock.call_args.args[0], "locations_export.csv")
        self.assertEqual(location_response_mock.call_args.args[2], [["WH-A", "Z1", "A1", "S1", "n1", "Red"]])

        categories_qs = mock.MagicMock()
        categories_qs.all.return_value = [
            SimpleNamespace(name="Child", parent=SimpleNamespace(name="Parent"))
        ]
        with mock.patch(
            "wms.exports.ProductCategory.objects.select_related",
            return_value=categories_qs,
        ):
            with mock.patch(
                "wms.exports._build_csv_response",
                return_value="categories-response",
            ) as category_response_mock:
                self.assertEqual(exports.export_categories_csv(), "categories-response")
        self.assertEqual(category_response_mock.call_args.args[0], "categories_export.csv")
        self.assertEqual(category_response_mock.call_args.args[2], [["Child", "Parent"]])

        with mock.patch(
            "wms.exports.Warehouse.objects.all",
            return_value=[SimpleNamespace(name="WH-A", code="A"), SimpleNamespace(name="WH-B", code="")],
        ):
            with mock.patch(
                "wms.exports._build_csv_response",
                return_value="warehouses-response",
            ) as warehouse_response_mock:
                self.assertEqual(exports.export_warehouses_csv(), "warehouses-response")
        self.assertEqual(warehouse_response_mock.call_args.args[0], "warehouses_export.csv")
        self.assertEqual(warehouse_response_mock.call_args.args[2], [["WH-A", "A"], ["WH-B", ""]])

    def test_export_contacts_csv_handles_contacts_with_and_without_addresses(self):
        contact_without_address = SimpleNamespace(
            contact_type="individual",
            title="Mr",
            first_name="John",
            last_name="Doe",
            name="John Doe",
            organization=None,
            role="Volunteer",
            email="john@example.com",
            email2="",
            phone="123",
            phone2="",
            use_organization_address=True,
            tags=SimpleNamespace(all=lambda: [SimpleNamespace(name="TagB"), SimpleNamespace(name="TagA")]),
            destination=None,
            get_effective_addresses=lambda: [],
            siret="",
            vat_number="",
            legal_registration_number="",
            asf_id="ASF-1",
            notes="note1",
        )

        address_1 = SimpleNamespace(
            label="HQ",
            address_line1="1 Street",
            address_line2="",
            postal_code="75000",
            city="Paris",
            region="IDF",
            country="France",
            phone="999",
            email="addr@example.com",
            is_default=True,
        )
        contact_with_addresses = SimpleNamespace(
            contact_type="association",
            title="",
            first_name="",
            last_name="",
            name="ASF",
            organization=SimpleNamespace(name="OrgX"),
            role="Partner",
            email="asf@example.com",
            email2="",
            phone="456",
            phone2="",
            use_organization_address=False,
            tags=SimpleNamespace(all=lambda: []),
            destination=SimpleNamespace(__str__=lambda self: "Paris - France"),
            addresses=SimpleNamespace(all=lambda: [address_1]),
            siret="S1",
            vat_number="V1",
            legal_registration_number="L1",
            asf_id="ASF-2",
            notes="note2",
        )

        contacts_qs = mock.MagicMock()
        contacts_qs.prefetch_related.return_value = [contact_without_address, contact_with_addresses]
        with mock.patch(
            "wms.exports.Contact.objects.select_related",
            return_value=contacts_qs,
        ):
            with mock.patch(
                "wms.exports._build_csv_response",
                return_value="contacts-response",
            ) as response_mock:
                result = exports.export_contacts_csv()

        self.assertEqual(result, "contacts-response")
        self.assertEqual(response_mock.call_args.args[0], "contacts_export.csv")
        rows = response_mock.call_args.args[2]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "individual")
        self.assertEqual(rows[0][12], "TagA|TagB")
        self.assertEqual(rows[0][18], "")
        self.assertEqual(rows[1][0], "association")
        self.assertEqual(rows[1][5], "OrgX")
        self.assertEqual(rows[1][18], "HQ")
        self.assertEqual(rows[1][27], "true")

    def test_export_users_csv(self):
        fake_user_model = SimpleNamespace(
            objects=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        username="user1",
                        email="u1@example.com",
                        first_name="U",
                        last_name="One",
                        is_staff=True,
                        is_superuser=False,
                        is_active=True,
                    )
                ]
            )
        )
        with mock.patch("wms.exports.get_user_model", return_value=fake_user_model):
            with mock.patch(
                "wms.exports._build_csv_response",
                return_value="users-response",
            ) as response_mock:
                result = exports.export_users_csv()

        self.assertEqual(result, "users-response")
        self.assertEqual(response_mock.call_args.args[0], "users_export.csv")
        self.assertEqual(
            response_mock.call_args.args[2],
            [["user1", "u1@example.com", "U", "One", "true", "false", "true", ""]],
        )
