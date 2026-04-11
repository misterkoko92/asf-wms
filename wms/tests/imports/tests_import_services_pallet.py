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
        created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
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
        self.assertEqual(incomplete_product_ids, [])

    def test_apply_pallet_listing_import_handles_override_and_target_selection_errors(self):
        payload_override = {
            "apply": True,
            "row_index": 3,
            "row_data": {"quantity": "2"},
            "override_code": "BAD-CODE",
            "selection": "",
        }
        with mock.patch("wms.import_services_pallet.resolve_product", return_value=None):
            created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
                [payload_override],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 3: produit introuvable pour BAD-CODE."])
        self.assertIsNone(receipt)
        self.assertEqual(incomplete_product_ids, [])

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
            created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
                [payload_target],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 4: produit cible introuvable."])
        self.assertIsNone(receipt)
        self.assertEqual(incomplete_product_ids, [])

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
            created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
                [payload_new_error],
                user=self.user,
                warehouse=self.warehouse,
                receipt_meta={},
            )
        self.assertEqual(created, 0)
        self.assertEqual(errors, ["Ligne 5: Produit invalide"])
        self.assertIsNone(receipt)
        self.assertEqual(incomplete_product_ids, [])

        payload_no_product = {
            "apply": True,
            "row_index": 6,
            "row_data": {"quantity": "1"},
            "selection": "",
        }
        created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
            [payload_no_product],
            user=self.user,
            warehouse=self.warehouse,
            receipt_meta={},
        )
        self.assertEqual(created, 0)
        self.assertEqual(errors, ["Ligne 6: produit non déterminé."])
        self.assertIsNone(receipt)
        self.assertEqual(incomplete_product_ids, [])

    def test_apply_pallet_listing_import_skips_detected_summary_rows(self):
        payload_summary = {
            "apply": True,
            "row_index": 7,
            "row_data": {
                "name": "VALORISATION DU DON",
                "quantity": "181",
                "ean": "",
            },
            "selection": "",
        }

        created, skipped, errors, receipt, incomplete_product_ids = apply_pallet_listing_import(
            [payload_summary],
            user=self.user,
            warehouse=self.warehouse,
            receipt_meta={},
        )

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(errors, [])
        self.assertIsNone(receipt)
        self.assertEqual(incomplete_product_ids, [])

    def test_apply_pallet_listing_import_uses_listing_buffer_when_no_location_is_available(self):
        product = SimpleNamespace(default_location=None, storage_conditions="Cold")
        payload = {
            "apply": True,
            "row_index": 7,
            "row_data": {"quantity": "3"},
            "override_code": "SKU-7",
        }
        receipt = SimpleNamespace(id=51, reference="RCP-51")
        with mock.patch("wms.import_services_pallet.resolve_product", return_value=product):
            with mock.patch(
                "wms.import_services_pallet.resolve_listing_location", return_value=None
            ):
                with mock.patch(
                    "wms.import_services_pallet.get_or_create_listing_buffer_location",
                    return_value=SimpleNamespace(id=77),
                ) as buffer_mock:
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
                            ) as line_create_mock:
                                with mock.patch("wms.import_services_pallet.receive_receipt_line"):
                                    (
                                        created,
                                        skipped,
                                        errors,
                                        out_receipt,
                                        incomplete_product_ids,
                                    ) = apply_pallet_listing_import(
                                        [payload],
                                        user=self.user,
                                        warehouse=self.warehouse,
                                        receipt_meta={},
                                    )
        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])
        self.assertIs(out_receipt, receipt)
        self.assertEqual(incomplete_product_ids, [])
        buffer_mock.assert_called_once_with(self.warehouse)
        self.assertEqual(line_create_mock.call_args.kwargs["location"].id, 77)

    def test_apply_pallet_listing_import_marks_new_listing_products_incomplete(self):
        created_product = SimpleNamespace(
            id=81,
            default_location=None,
            storage_conditions="",
            is_incomplete=True,
        )
        payload = {
            "apply": True,
            "row_index": 8,
            "row_data": {"name": "Mask", "quantity": "2", "ean": "EAN-8"},
            "selection": "new",
        }
        receipt = SimpleNamespace(id=80, reference="RCP-80")

        def _fake_import(row, *, user=None):
            self.assertTrue(row["is_incomplete"])
            self.assertEqual(row["ean"], "EAN-8")
            self.assertNotIn("quantity", row)
            return created_product, True, []

        with mock.patch("wms.import_services_pallet.import_product_row", side_effect=_fake_import):
            with mock.patch(
                "wms.import_services_pallet.resolve_listing_location",
                return_value=None,
            ):
                with mock.patch(
                    "wms.import_services_pallet.get_or_create_listing_buffer_location",
                    return_value=SimpleNamespace(id=88),
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
                                return_value=SimpleNamespace(id=8),
                            ):
                                with mock.patch("wms.import_services_pallet.receive_receipt_line"):
                                    (
                                        created,
                                        skipped,
                                        errors,
                                        out_receipt,
                                        incomplete_product_ids,
                                    ) = apply_pallet_listing_import(
                                        [payload],
                                        user=self.user,
                                        warehouse=self.warehouse,
                                        receipt_meta={},
                                    )

        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])
        self.assertIs(out_receipt, receipt)
        self.assertEqual(incomplete_product_ids, [81])

    def test_apply_pallet_listing_import_success_reuses_receipt_and_defaults_dates(self):
        product_1 = SimpleNamespace(
            default_location=SimpleNamespace(id=1), storage_conditions="Cold"
        )
        product_2 = SimpleNamespace(default_location=SimpleNamespace(id=2), storage_conditions="")
        payloads = [
            {
                "apply": True,
                "row_index": 8,
                "row_data": {"quantity": "2"},
                "selection": "product:11",
            },
            {
                "apply": True,
                "row_index": 9,
                "row_data": {"quantity": "1"},
                "selection": "product:12",
            },
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
                        with mock.patch(
                            "wms.import_services_pallet.ReceiptLine.objects.create"
                        ) as line_create_mock:
                            with mock.patch(
                                "wms.import_services_pallet.receive_receipt_line"
                            ) as receive_mock:
                                with mock.patch(
                                    "wms.import_services_pallet.timezone.localdate",
                                    return_value=date(2026, 1, 20),
                                ):
                                    (
                                        created,
                                        skipped,
                                        errors,
                                        out_receipt,
                                        incomplete_product_ids,
                                    ) = apply_pallet_listing_import(
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
        self.assertEqual(incomplete_product_ids, [])
        receipt_create_mock.assert_called_once_with(
            receipt_type=mock.ANY,
            status=mock.ANY,
            source_contact="source-contact",
            carrier_contact="carrier-contact",
            received_on=date(2026, 1, 20),
            pallet_count=4,
            transport_request_date=None,
            conformity_status=mock.ANY,
            notes="",
            warehouse=self.warehouse,
            created_by=self.user,
        )
        self.assertEqual(line_create_mock.call_count, 2)
        self.assertEqual(line_create_mock.call_args_list[0].kwargs["storage_conditions"], "Cold")
        self.assertEqual(line_create_mock.call_args_list[1].kwargs["storage_conditions"], "")
        self.assertEqual(receive_mock.call_count, 2)

    def test_apply_pallet_listing_import_reuses_selected_receipt_without_creating_new_one(self):
        product = SimpleNamespace(
            default_location=SimpleNamespace(id=1),
            storage_conditions="Cold",
        )
        existing_receipt = SimpleNamespace(id=60, reference="RCP-60")
        payload = {
            "apply": True,
            "row_index": 11,
            "row_data": {"quantity": "2"},
            "override_code": "SKU-11",
        }

        with mock.patch("wms.import_services_pallet.resolve_product", return_value=product):
            with mock.patch(
                "wms.import_services_pallet.resolve_listing_location",
                return_value=SimpleNamespace(id=10),
            ):
                with mock.patch(
                    "wms.import_services_pallet.Receipt.objects.create"
                ) as receipt_create_mock:
                    with mock.patch(
                        "wms.import_services_pallet.ReceiptLine.objects.create",
                        return_value=SimpleNamespace(id=11),
                    ) as line_create_mock:
                        with mock.patch(
                            "wms.import_services_pallet.receive_receipt_line"
                        ) as receive_mock:
                            created, skipped, errors, out_receipt, incomplete_product_ids = (
                                apply_pallet_listing_import(
                                    [payload],
                                    user=self.user,
                                    warehouse=self.warehouse,
                                    receipt_meta={},
                                    existing_receipt=existing_receipt,
                                )
                            )

        self.assertEqual(created, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, [])
        self.assertIs(out_receipt, existing_receipt)
        self.assertEqual(incomplete_product_ids, [])
        receipt_create_mock.assert_not_called()
        self.assertIs(line_create_mock.call_args.kwargs["receipt"], existing_receipt)
        receive_mock.assert_called_once()

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
                                created, skipped, errors, out_receipt, incomplete_product_ids = (
                                    apply_pallet_listing_import(
                                        [payload],
                                        user=self.user,
                                        warehouse=self.warehouse,
                                        receipt_meta={},
                                    )
                                )

        self.assertEqual(created, 0)
        self.assertEqual(skipped, 0)
        self.assertEqual(errors, ["Ligne 10: Stock KO"])
        self.assertIs(out_receipt, receipt)
        self.assertEqual(incomplete_product_ids, [])
