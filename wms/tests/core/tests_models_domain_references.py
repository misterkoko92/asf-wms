from datetime import date
from unittest import mock

from django.db.models.functions import Length
from django.test import SimpleTestCase

from wms.models_domain import references


class ReferencesModuleTests(SimpleTestCase):
    def test_model_resolves_from_apps_registry(self):
        with mock.patch(
            "wms.models_domain.references.apps.get_model",
            return_value="ResolvedModel",
        ) as get_model_mock:
            model = references._model("Receipt")

        self.assertEqual(model, "ResolvedModel")
        get_model_mock.assert_called_once_with("wms", "Receipt")

    def test_generate_receipt_reference_delegates_with_expected_dependencies(self):
        with mock.patch.object(
            references,
            "_model",
            side_effect=["ReceiptModel", "ReceiptSeqModel", "ReceiptDonorSeqModel"],
        ) as model_mock, mock.patch.object(
            references.reference_sequences,
            "generate_receipt_reference",
            return_value="31-08-CON-05",
        ) as generate_mock:
            result = references.generate_receipt_reference(
                received_on=date(2031, 2, 1),
                source_contact="contact",
            )

        self.assertEqual(result, "31-08-CON-05")
        self.assertEqual(
            model_mock.call_args_list,
            [
                mock.call("Receipt"),
                mock.call("ReceiptSequence"),
                mock.call("ReceiptDonorSequence"),
            ],
        )
        kwargs = generate_mock.call_args.kwargs
        self.assertEqual(kwargs["received_on"], date(2031, 2, 1))
        self.assertEqual(kwargs["source_contact"], "contact")
        self.assertEqual(kwargs["receipt_model"], "ReceiptModel")
        self.assertEqual(kwargs["receipt_sequence_model"], "ReceiptSeqModel")
        self.assertEqual(kwargs["receipt_donor_sequence_model"], "ReceiptDonorSeqModel")
        self.assertIs(kwargs["transaction_module"], references.transaction)
        self.assertIs(kwargs["connection_obj"], references.connection)
        self.assertIs(kwargs["integrity_error"], references.IntegrityError)
        self.assertIs(kwargs["receipt_reference_re"], references.RECEIPT_REFERENCE_RE)
        self.assertIs(kwargs["localdate_fn"], references.timezone.localdate)

    def test_generate_shipment_reference_delegates_with_expected_dependencies(self):
        with mock.patch.object(
            references,
            "_model",
            side_effect=["ShipmentModel", "ShipmentSeqModel"],
        ) as model_mock, mock.patch.object(
            references.reference_sequences,
            "generate_shipment_reference",
            return_value="320124",
        ) as generate_mock:
            result = references.generate_shipment_reference()

        self.assertEqual(result, "320124")
        self.assertEqual(
            model_mock.call_args_list,
            [
                mock.call("Shipment"),
                mock.call("ShipmentSequence"),
            ],
        )
        kwargs = generate_mock.call_args.kwargs
        self.assertEqual(kwargs["shipment_model"], "ShipmentModel")
        self.assertEqual(kwargs["shipment_sequence_model"], "ShipmentSeqModel")
        self.assertIs(kwargs["transaction_module"], references.transaction)
        self.assertIs(kwargs["connection_obj"], references.connection)
        self.assertIs(kwargs["integrity_error"], references.IntegrityError)
        self.assertIs(kwargs["length_cls"], Length)
        self.assertIs(kwargs["localdate_fn"], references.timezone.localdate)
