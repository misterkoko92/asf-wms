from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.shipment_form_helpers import (
    build_carton_selection_data,
    build_shipment_edit_initial,
    build_shipment_edit_line_values,
    build_shipment_form_context,
    build_shipment_form_payload,
)


class ShipmentFormHelpersTests(SimpleTestCase):
    def test_build_shipment_form_payload_composes_all_sources(self):
        with mock.patch(
            "wms.shipment_form_helpers.build_product_options",
            return_value=[{"sku": "P1"}],
        ):
            with mock.patch(
                "wms.shipment_form_helpers.build_available_cartons",
                return_value=[{"id": 1, "code": "C-1"}],
            ):
                with mock.patch(
                    "wms.shipment_form_helpers.build_shipment_contact_payload",
                    return_value=([{"id": 10}], [{"id": 20}], [{"id": 30}]),
                ):
                    payload = build_shipment_form_payload()

        self.assertEqual(
            payload,
            (
                [{"sku": "P1"}],
                [{"id": 1, "code": "C-1"}],
                [{"id": 10}],
                [{"id": 20}],
                [{"id": 30}],
            ),
        )

    def test_build_carton_selection_data_without_assigned_options(self):
        available_cartons = [{"id": 1, "code": "C-1"}, {"id": 2, "code": "C-2"}]

        cartons_json, allowed_ids = build_carton_selection_data(available_cartons, None)

        self.assertEqual(cartons_json, available_cartons)
        self.assertEqual(allowed_ids, {"1", "2"})

    def test_build_carton_selection_data_with_assigned_options_merges_unique_ids(self):
        available_cartons = [{"id": 1, "code": "C-1"}]
        assigned_cartons = [{"id": 1, "code": "C-1"}, {"id": 3, "code": "C-3"}]

        cartons_json, allowed_ids = build_carton_selection_data(
            available_cartons,
            assigned_cartons,
        )

        self.assertEqual(allowed_ids, {"1", "3"})
        by_id = {str(item["id"]): item for item in cartons_json}
        self.assertEqual(set(by_id.keys()), {"1", "3"})
        self.assertEqual(by_id["3"]["code"], "C-3")

    def test_build_shipment_edit_initial_prefers_destination_correspondent_contact(self):
        shipper = SimpleNamespace(id=11)
        recipient = SimpleNamespace(id=22)
        destination_correspondent = SimpleNamespace(id=33)
        destination = SimpleNamespace(
            correspondent_contact_id=destination_correspondent.id,
            correspondent_contact=destination_correspondent,
        )
        shipment = SimpleNamespace(
            shipper_name="Shipper Name",
            recipient_name="Recipient Name",
            correspondent_name="Corr Name",
            destination=destination,
            destination_id=99,
        )

        with mock.patch(
            "wms.shipment_form_helpers.resolve_contact_by_name",
            side_effect=[shipper, recipient],
        ) as resolve_mock:
            initial = build_shipment_edit_initial(shipment, assigned_cartons=[1, 2])

        self.assertEqual(initial["destination"], 99)
        self.assertEqual(initial["shipper_contact"], 11)
        self.assertEqual(initial["recipient_contact"], 22)
        self.assertEqual(initial["correspondent_contact"], 33)
        self.assertEqual(initial["carton_count"], 2)
        self.assertEqual(resolve_mock.call_count, 2)

    def test_build_shipment_edit_initial_falls_back_to_name_resolution(self):
        shipper = SimpleNamespace(id=11)
        recipient = None
        correspondent = SimpleNamespace(id=44)
        shipment = SimpleNamespace(
            shipper_name="Shipper Name",
            recipient_name="Recipient Name",
            correspondent_name="Corr Name",
            destination=None,
            destination_id=None,
        )

        with mock.patch(
            "wms.shipment_form_helpers.resolve_contact_by_name",
            side_effect=[shipper, recipient, correspondent],
        ) as resolve_mock:
            initial = build_shipment_edit_initial(shipment, assigned_cartons=[])

        self.assertEqual(initial["destination"], None)
        self.assertEqual(initial["shipper_contact"], 11)
        self.assertEqual(initial["recipient_contact"], None)
        self.assertEqual(initial["correspondent_contact"], 44)
        self.assertEqual(initial["carton_count"], 1)
        self.assertEqual(resolve_mock.call_count, 3)

    def test_build_shipment_edit_line_values_uses_assigned_cartons(self):
        assigned_cartons = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        line_values = build_shipment_edit_line_values(assigned_cartons, carton_count=3)

        self.assertEqual(
            line_values,
            [
                {"carton_id": 1, "product_code": "", "quantity": ""},
                {"carton_id": 2, "product_code": "", "quantity": ""},
            ],
        )

    def test_build_shipment_edit_line_values_falls_back_to_generated_lines(self):
        with mock.patch(
            "wms.shipment_form_helpers.build_shipment_line_values",
            return_value=[{"carton_id": "", "product_code": "P1", "quantity": "2"}],
        ) as line_values_mock:
            line_values = build_shipment_edit_line_values([], carton_count=4)

        self.assertEqual(line_values, [{"carton_id": "", "product_code": "P1", "quantity": "2"}])
        line_values_mock.assert_called_once_with(4)

    def test_build_shipment_form_context_returns_expected_mapping(self):
        context = build_shipment_form_context(
            form=object(),
            product_options=[{"sku": "P1"}],
            cartons_json=[{"id": 1}],
            carton_count=2,
            line_values=[{"product_code": "P1"}],
            line_errors={"1": ["Erreur"]},
            destinations_json=[{"id": 10}],
            recipient_contacts_json=[{"id": 20}],
            correspondent_contacts_json=[{"id": 30}],
        )

        self.assertEqual(context["products_json"], [{"sku": "P1"}])
        self.assertEqual(context["cartons_json"], [{"id": 1}])
        self.assertEqual(context["carton_count"], 2)
        self.assertEqual(context["line_values"], [{"product_code": "P1"}])
        self.assertEqual(context["line_errors"], {"1": ["Erreur"]})
        self.assertEqual(context["destinations_json"], [{"id": 10}])
        self.assertEqual(context["recipient_contacts_json"], [{"id": 20}])
        self.assertEqual(context["correspondent_contacts_json"], [{"id": 30}])
