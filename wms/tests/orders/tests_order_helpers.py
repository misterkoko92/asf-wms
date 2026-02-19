from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactAddress
from wms.models import (
    AssociationProfile,
    CartonFormat,
    DocumentType,
    Order,
    OrderDocumentType,
    Product,
)
from wms.order_helpers import (
    attach_order_documents_to_shipment,
    build_carton_format_data,
    build_order_creator_info,
    build_order_line_items,
    build_order_line_estimates,
    build_order_product_rows,
    estimate_cartons_for_line,
)


class OrderHelpersTests(TestCase):
    def _create_order(
        self,
        *,
        created_by=None,
        association_contact=None,
        recipient_contact=None,
    ):
        return Order.objects.create(
            created_by=created_by,
            association_contact=association_contact,
            recipient_contact=recipient_contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name="Association Dest",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def _create_product(self, sku, name, *, weight_g=None, volume_cm3=None):
        return Product.objects.create(
            sku=sku,
            name=name,
            weight_g=weight_g,
            volume_cm3=volume_cm3,
            qr_code_image="qr_codes/test.png",
        )

    def test_build_order_creator_info_uses_association_profile_contact_and_address_fallback(self):
        user = get_user_model().objects.create_user(
            username="order-creator-profile",
            email="creator@example.com",
            password="pass1234",
        )
        contact = Contact.objects.create(
            name="Association Profile",
            phone="",
            email="",
            is_active=True,
        )
        ContactAddress.objects.create(
            contact=contact,
            address_line1="10 Rue Profile",
            city="Paris",
            country="France",
            phone="0101010101",
            email="profile-address@example.com",
            is_default=True,
        )
        AssociationProfile.objects.create(user=user, contact=contact)
        order = self._create_order(created_by=user)

        info = build_order_creator_info(order)

        self.assertEqual(
            info,
            {
                "name": "Association Profile",
                "phone": "0101010101",
                "email": "creator@example.com",
            },
        )

    def test_build_order_creator_info_falls_back_to_recipient_contact(self):
        user = get_user_model().objects.create_user(
            username="order-creator-recipient",
            email="recipient-user@example.com",
            password="pass1234",
        )
        recipient = Contact.objects.create(
            name="Recipient Contact",
            phone="0202020202",
            email="recipient@example.com",
            is_active=True,
        )
        order = self._create_order(created_by=user, recipient_contact=recipient)

        info = build_order_creator_info(order)

        self.assertEqual(
            info,
            {
                "name": "Recipient Contact",
                "phone": "0202020202",
                "email": "recipient@example.com",
            },
        )

    def test_build_order_creator_info_falls_back_to_user_identity_when_no_contact(self):
        user = get_user_model().objects.create_user(
            username="order-creator-user",
            email="fallback-user@example.com",
            password="pass1234",
            first_name="Test",
            last_name="User",
        )
        order = self._create_order(created_by=user)

        info = build_order_creator_info(order)

        self.assertEqual(
            info,
            {
                "name": "Test User",
                "phone": "",
                "email": "fallback-user@example.com",
            },
        )

    def test_attach_order_documents_to_shipment_returns_early_without_inputs(self):
        attach_order_documents_to_shipment(None, object())
        attach_order_documents_to_shipment(object(), None)

    def test_attach_order_documents_to_shipment_copies_only_wanted_unique_documents(self):
        shipment = SimpleNamespace(id=1)
        new_file = SimpleNamespace(name="new.pdf")
        duplicated_file = SimpleNamespace(name="dup.pdf")
        docs = [
            SimpleNamespace(doc_type=OrderDocumentType.DONATION_ATTESTATION, file=None),
            SimpleNamespace(
                doc_type=OrderDocumentType.DONATION_ATTESTATION, file=duplicated_file
            ),
            SimpleNamespace(
                doc_type=OrderDocumentType.HUMANITARIAN_ATTESTATION, file=new_file
            ),
        ]
        order = SimpleNamespace(documents=mock.MagicMock())
        order.documents.filter.return_value = docs
        filter_result = mock.MagicMock()
        filter_result.values_list.return_value = ["dup.pdf"]

        with mock.patch(
            "wms.order_helpers.Document.objects.filter",
            return_value=filter_result,
        ) as filter_mock:
            with mock.patch("wms.order_helpers.Document.objects.create") as create_mock:
                attach_order_documents_to_shipment(order, shipment)

        filter_mock.assert_called_once_with(
            shipment=shipment, doc_type=DocumentType.ADDITIONAL
        )
        order.documents.filter.assert_called_once()
        create_mock.assert_called_once_with(
            shipment=shipment,
            doc_type=DocumentType.ADDITIONAL,
            file=new_file,
        )

    def test_estimate_cartons_for_line_uses_single_weight_constraint(self):
        product = self._create_product(
            "ORDER-EST-WEIGHT",
            "Produit Poids",
            weight_g=500,
            volume_cm3=None,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Poids",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )

        estimate = estimate_cartons_for_line(
            product=product,
            quantity=3,
            carton_format=carton_format,
        )

        self.assertEqual(estimate, 2)

    def test_estimate_cartons_for_line_returns_none_without_carton_format(self):
        product = self._create_product(
            "ORDER-EST-NO-FORMAT",
            "Produit Sans Format",
            weight_g=500,
        )
        estimate = estimate_cartons_for_line(
            product=product,
            quantity=2,
            carton_format=None,
        )
        self.assertIsNone(estimate)

    def test_estimate_cartons_for_line_uses_weight_and_volume_limits(self):
        product = self._create_product(
            "ORDER-EST-BOTH",
            "Produit Contraintes",
            weight_g=500,
            volume_cm3=6000,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Double Contrainte",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )

        estimate = estimate_cartons_for_line(
            product=product,
            quantity=3,
            carton_format=carton_format,
        )

        self.assertEqual(estimate, 2)

    def test_estimate_cartons_for_line_returns_none_when_no_constraints_available(self):
        product = self._create_product(
            "ORDER-EST-NONE",
            "Produit Sans Contraintes",
            weight_g=None,
            volume_cm3=None,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Vide",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )

        estimate = estimate_cartons_for_line(
            product=product,
            quantity=2,
            carton_format=carton_format,
        )

        self.assertIsNone(estimate)

    def test_build_carton_format_data_handles_none_and_returns_serializable_payload(self):
        self.assertIsNone(build_carton_format_data(None))
        carton_format = CartonFormat.objects.create(
            name="Format Serialise",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=8000,
        )
        payload = build_carton_format_data(carton_format)
        self.assertEqual(
            payload,
            {
                "length_cm": 40.0,
                "width_cm": 30.0,
                "height_cm": 20.0,
                "max_weight_g": 8000.0,
                "name": "Format Serialise",
            },
        )

    def test_build_order_line_items_collects_valid_lines_and_errors(self):
        product_invalid = self._create_product("ORDER-LINE-A", "Produit A", weight_g=100)
        product_stock = self._create_product("ORDER-LINE-B", "Produit B", weight_g=100)
        product_valid = self._create_product("ORDER-LINE-C", "Produit C", weight_g=100)

        post_data = {
            f"product_{product_invalid.id}_qty": "abc",
            f"product_{product_stock.id}_qty": "5",
            f"product_{product_valid.id}_qty": "2",
            "product_999999_qty": "1",
        }
        product_options = [
            {"id": product_invalid.id},
            {"id": product_stock.id},
            {"id": product_valid.id},
            {"id": 999999},
            {"id": None},
        ]
        product_by_id = {
            product_invalid.id: product_invalid,
            product_stock.id: product_stock,
            product_valid.id: product_valid,
        }
        available_by_id = {
            product_invalid.id: 10,
            product_stock.id: 3,
            product_valid.id: 2,
            999999: 1,
        }

        line_items, line_quantities, line_errors = build_order_line_items(
            post_data,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )

        self.assertEqual(line_quantities[str(product_invalid.id)], "abc")
        self.assertEqual(line_quantities[str(product_stock.id)], "5")
        self.assertEqual(line_quantities[str(product_valid.id)], "2")
        self.assertEqual(line_quantities["999999"], "1")
        self.assertEqual(line_errors[str(product_invalid.id)], "Quantité invalide.")
        self.assertEqual(line_errors[str(product_stock.id)], "Stock insuffisant.")
        self.assertEqual(line_items, [(product_valid, 2)])

    def test_build_order_line_items_ignorés_empty_quantities(self):
        product = self._create_product("ORDER-LINE-EMPTY", "Produit Vide", weight_g=100)
        line_items, line_quantities, line_errors = build_order_line_items(
            {},
            product_options=[{"id": product.id}],
            product_by_id={product.id: product},
            available_by_id={product.id: 3},
        )
        self.assertEqual(line_items, [])
        self.assertEqual(line_quantities, {})
        self.assertEqual(line_errors, {})

    def test_build_order_product_rows_computes_estimates_and_total(self):
        product_estimated = self._create_product(
            "ORDER-ROW-A",
            "Produit Estime",
            weight_g=500,
            volume_cm3=None,
        )
        product_invalid_qty = self._create_product(
            "ORDER-ROW-B",
            "Produit Sans Estime",
            weight_g=300,
            volume_cm3=None,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Estime",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )
        product_options = [
            {"id": None, "name": "Ignore", "available_stock": 0},
            {"id": product_estimated.id, "name": "Produit Estime", "available_stock": 5},
            {
                "id": product_invalid_qty.id,
                "name": "Produit Sans Estime",
                "available_stock": 3,
            },
        ]
        product_by_id = {
            product_estimated.id: product_estimated,
            product_invalid_qty.id: product_invalid_qty,
        }
        line_quantities = {
            str(product_estimated.id): "3",
            str(product_invalid_qty.id): "bad",
        }

        rows, total = build_order_product_rows(
            product_options,
            product_by_id,
            line_quantities,
            carton_format,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], product_estimated.id)
        self.assertEqual(rows[0]["quantity"], "3")
        self.assertEqual(rows[0]["estimate"], 2)
        self.assertEqual(rows[1]["id"], product_invalid_qty.id)
        self.assertEqual(rows[1]["quantity"], "bad")
        self.assertIsNone(rows[1]["estimate"])
        self.assertEqual(total, 2)

    def test_build_order_product_rows_sets_total_none_when_no_estimate(self):
        product = self._create_product(
            "ORDER-ROW-NONE",
            "Produit Sans Estimation",
            weight_g=None,
            volume_cm3=None,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Sans Estimation",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )
        rows, total = build_order_product_rows(
            [{"id": product.id, "name": product.name, "available_stock": 2}],
            {product.id: product},
            {str(product.id): "2"},
            carton_format,
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["estimate"])
        self.assertIsNone(total)

    def test_build_order_line_estimates_with_custom_key_and_total(self):
        product_a = self._create_product(
            "ORDER-EST-LINE-A",
            "Produit Ligne A",
            weight_g=500,
            volume_cm3=None,
        )
        product_b = self._create_product(
            "ORDER-EST-LINE-B",
            "Produit Ligne B",
            weight_g=None,
            volume_cm3=None,
        )
        carton_format = CartonFormat.objects.create(
            name="Format Ligne",
            length_cm=40,
            width_cm=30,
            height_cm=20,
            max_weight_g=1000,
        )
        lines = [
            SimpleNamespace(product=product_a, quantity=3),
            SimpleNamespace(product=product_b, quantity=2),
        ]

        rows, total = build_order_line_estimates(
            lines,
            carton_format,
            estimate_key="cartons_estimated",
        )

        self.assertEqual(total, 2)
        self.assertEqual(rows[0]["product"], "Produit Ligne A")
        self.assertEqual(rows[0]["cartons_estimated"], 2)
        self.assertIsNone(rows[1]["cartons_estimated"])

    def test_build_order_line_estimates_supports_empty_key_and_none_total(self):
        product = self._create_product(
            "ORDER-EST-LINE-NONE",
            "Produit Ligne None",
            weight_g=None,
            volume_cm3=None,
        )
        lines = [SimpleNamespace(product=product, quantity=1)]

        rows, total = build_order_line_estimates(
            lines,
            carton_format=None,
            estimate_key=None,
        )

        self.assertEqual(rows, [{"product": "Produit Ligne None", "quantity": 1}])
        self.assertIsNone(total)
