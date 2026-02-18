from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.import_services_pallet import apply_pallet_listing_import
from wms.services import StockError


class ImportServicesPalletTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(id=1, username="import-user")
        self.warehouse = SimpleNamespace(name="Main")

    def test_apply_pallet_listing_import_skips_rows_and_validates_quantity(self):
        created, skipped, errors, receipt = apply_pallet_listing_import(
            [
                {"apply": False},
                {"apply": True, "row_index": 2, "row_data": {"quantity": "0"}},
            ],
            user=self.user,
            warehouse=self.warehouse,
            receipt_meta={},
        )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(errors, ["Ligne 2: quantité invalide."])
        self.assertIsNone(receipt)

    def test_apply_pallet_listing_import_handles_override_and_target_selection_errors(self):
        payload_override = {
            "apply": True,
            "row_index": 3,
            "row_data": {"quantity": "2"},
            "override_code": "BAD-CODE",
            "selection": "",
        }
        with mock.patch("wms.import_services_pallet.resolve_product", return_value=None):
            created, skipped, errors, receipt = apply_pallet_listing_import(
                [payload_override],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 3: produit introuvable pour BAD-CODE."])
        self.assertIsNone(receipt)

        payload_target = {
            "apply": True,
            "row_index": 4,
            "row_data": {"quantity": "1"},
            "selection": "product:99",
        }
        with mock.patch(
            "wms.import_services_pallet.Product.objects.filter",
            return_value=SimpleNamespace(first=lambda: None),
        ):
            created, skipped, errors, receipt = apply_pallet_listing_import(
                [payload_target],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 4: produit cible introuvable."])
        self.assertIsNone(receipt)

    def test_apply_pallet_listing_import_handles_new_product_errors_and_undetermined_product(self):
        payload_new_error = {
            "apply": True,
            "row_index": 5,
            "row_data": {"quantity": "2", "name": "Mask"},
            "selection": "new",
        }
        with mock.patch(
            "wms.import_services_pallet.import_product_row",
            side_effect=ValueError("Produit invalide"),
        ):
            created, skipped, errors, receipt = apply_pallet_listing_import(
                [payload_new_error],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(errors, ["Ligne 5: Produit invalide"])
        self.assertIsNone(receipt)

        payload_no_product = {
            "apply": True,
            "row_index": 6,
            "row_data": {"quantity": "1"},
            "selection": "",
        }
        created, skipped, errors, receipt = apply_pallet_listing_import(
            [payload_no_product],
            user=self.user,
            warehouse=self.warehouse,
            receipt_meta={},
        )
        self.assertEqual(created, 0)
        self.assertEqual(errors, ["Ligne 6: produit non déterminé."])
        self.assertIsNone(receipt)

    def test_apply_pallet_listing_import_requires_location_when_none_resolved(self):
        product = SimpleNamespace(default_location=None, storage_conditions="Cold")
        payload = {
            "apply": True,
            "row_index": 7,
            "row_data": {"quantity": "3"},
            "override_code": "SKU-7",
        }
        with mock.patch("wms.import_services_pallet.resolve_product", return_value=product):
            with mock.patch("wms.import_services_pallet.resolve_listing_location", return_value=None):
                created, skipped, errors, receipt = apply_pallet_listing_import(
                    [payload],
                    user=self.user,
                    warehouse=self.warehouse,
                    receipt_meta={},
                )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 7: Emplacement requis pour réception."])
        self.assertIsNone(receipt)

    def test_apply_pallet_listing_import_success_reuses_receipt_and_defaults_dates(self):
        product_1 = SimpleNamespace(default_location=SimpleNamespace(id=1), storage_conditions="Cold")
        product_2 = SimpleNamespace(default_location=SimpleNamespace(id=2), storage_conditions="")
        payloads = [
            {"apply": True, "row_index": 8, "row_data": {"quantity": "2"}, "selection": "product:11"},
            {"apply": True, "row_index": 9, "row_data": {"quantity": "1"}, "selection": "product:12"},
        ]
        receipt = SimpleNamespace(id=50, reference="RCP-50")
        source_qs = SimpleNamespace(first=lambda: "source-contact")
        carrier_qs = SimpleNamespace(first=lambda: "carrier-contact")
        product_qs_1 = SimpleNamespace(first=lambda: product_1)
        product_qs_2 = SimpleNamespace(first=lambda: product_2)

        with mock.patch(
            "wms.import_services_pallet.Product.objects.filter",
            side_effect=[product_qs_1, product_qs_2],
        ):
            with mock.patch(
                "wms.import_services_pallet.resolve_listing_location",
                side_effect=[SimpleNamespace(id=10), None],
            ):
                with mock.patch(
                    "wms.import_services_pallet.Contact.objects.filter",
                    side_effect=[source_qs, carrier_qs],
                ):
                    with mock.patch(
                        "wms.import_services_pallet.Receipt.objects.create",
                        return_value=receipt,
                    ) as receipt_create_mock:
                        with mock.patch("wms.import_services_pallet.ReceiptLine.objects.create") as line_create_mock:
                            with mock.patch("wms.import_services_pallet.receive_receipt_line") as receive_mock:
                                with mock.patch(
                                    "wms.import_services_pallet.timezone.localdate",
                                    return_value=date(2026, 1, 20),
                                ):
                                    created, skipped, errors, out_receipt = apply_pallet_listing_import(
                                        payloads,
                                        user=self.user,
                                        warehouse=self.warehouse,
                                        receipt_meta={
                                            "source_contact_id": 1,
                                            "carrier_contact_id": 2,
                                            "pallet_count": 4,
                                        },
                                    )

        self.assertEqual(created, 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])
        self.assertIs(out_receipt, receipt)
        receipt_create_mock.assert_called_once_with(
            receipt_type=mock.ANY,
            status=mock.ANY,
            source_contact="source-contact",
            carrier_contact="carrier-contact",
            received_on=date(2026, 1, 20),
            pallet_count=4,
            transport_request_date=None,
            warehouse=self.warehouse,
            created_by=self.user,
        )
        self.assertEqual(line_create_mock.call_count, 2)
        self.assertEqual(line_create_mock.call_args_list[0].kwargs["storage_conditions"], "Cold")
        self.assertEqual(line_create_mock.call_args_list[1].kwargs["storage_conditions"], "")
        self.assertEqual(receive_mock.call_count, 2)

    def test_apply_pallet_listing_import_handles_stock_error(self):
        product = SimpleNamespace(default_location=SimpleNamespace(id=1), storage_conditions="Cold")
        payload = {
            "apply": True,
            "row_index": 10,
            "row_data": {"quantity": "2"},
            "override_code": "SKU-10",
        }
        receipt = SimpleNamespace(id=70, reference="RCP-70")
        with mock.patch("wms.import_services_pallet.resolve_product", return_value=product):
            with mock.patch(
                "wms.import_services_pallet.resolve_listing_location",
                return_value=SimpleNamespace(id=99),
            ):
                with mock.patch(
                    "wms.import_services_pallet.Contact.objects.filter",
                    return_value=SimpleNamespace(first=lambda: None),
                ):
                    with mock.patch(
                        "wms.import_services_pallet.Receipt.objects.create",
                        return_value=receipt,
                    ):
                        with mock.patch(
                            "wms.import_services_pallet.ReceiptLine.objects.create",
                            return_value=SimpleNamespace(id=1),
                        ):
                            with mock.patch(
                                "wms.import_services_pallet.receive_receipt_line",
                                side_effect=StockError("Stock KO"),
                            ):
                                created, skipped, errors, out_receipt = apply_pallet_listing_import(
                                    [payload],
                                    user=self.user,
                                    warehouse=self.warehouse,
                                    receipt_meta={},
                                )

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 10: Stock KO"])
        self.assertIs(out_receipt, receipt)
