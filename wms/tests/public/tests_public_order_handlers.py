from unittest import mock

from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from contacts.models import Contact
from wms.models import Order, Product, PublicOrderLink
from wms.public_order_handlers import create_public_order, send_public_order_notifications


class PublicOrderHandlersTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.link = PublicOrderLink.objects.create(label="Public link")

    def _form_data(self, **overrides):
        data = {
            "association_name": "Association Public",
            "association_email": "association@example.com",
            "association_phone": "0102030405",
            "association_line1": "1 Rue Test",
            "association_line2": "Bat A",
            "association_postal_code": "75001",
            "association_city": "Paris",
            "association_country": "France",
            "association_notes": "Besoin prioritaire",
        }
        data.update(overrides)
        return data

    def _request_with_messages(self):
        request = self.factory.get("/scan/public-order/")
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request

    def test_create_public_order_creates_order_lines_and_calls_services(self):
        contact = Contact.objects.create(
            name="Association Public",
            email="association@example.com",
            phone="0102030405",
        )
        product_a = Product.objects.create(
            sku="P-ORDER-A",
            name="Produit A",
            qr_code_image="qr_codes/test.png",
        )
        product_b = Product.objects.create(
            sku="P-ORDER-B",
            name="Produit B",
            qr_code_image="qr_codes/test.png",
        )
        line_items = [(product_a, 2), (product_b, 5)]

        with mock.patch(
            "wms.public_order_handlers.upsert_public_order_contact",
            return_value=contact,
        ) as upsert_mock:
            with mock.patch("wms.public_order_handlers.create_shipment_for_order") as shipment_mock:
                with mock.patch("wms.public_order_handlers.reserve_stock_for_order") as reserve_mock:
                    order, returned_contact = create_public_order(
                        link=self.link,
                        form_data=self._form_data(),
                        line_items=line_items,
                    )

        self.assertEqual(returned_contact.id, contact.id)
        self.assertEqual(order.public_link_id, self.link.id)
        self.assertEqual(order.recipient_name, "Association Public")
        self.assertEqual(order.destination_city, "Paris")
        self.assertEqual(order.destination_country, "France")
        self.assertEqual(
            order.destination_address,
            "1 Rue Test\nBat A\n75001 Paris\nFrance",
        )
        lines = list(order.lines.order_by("product__sku").values_list("product__sku", "quantity"))
        self.assertEqual(lines, [("P-ORDER-A", 2), ("P-ORDER-B", 5)])
        upsert_mock.assert_called_once()
        shipment_mock.assert_called_once_with(order=order)
        reserve_mock.assert_called_once_with(order=order)

    def test_create_public_order_defaults_destination_country_when_form_country_empty(self):
        contact = Contact.objects.create(name="Association Country", is_active=True)
        product = Product.objects.create(
            sku="P-ORDER-C",
            name="Produit C",
            qr_code_image="qr_codes/test.png",
        )

        with mock.patch(
            "wms.public_order_handlers.upsert_public_order_contact",
            return_value=contact,
        ):
            with mock.patch("wms.public_order_handlers.create_shipment_for_order"):
                with mock.patch("wms.public_order_handlers.reserve_stock_for_order"):
                    order, _ = create_public_order(
                        link=self.link,
                        form_data=self._form_data(association_country="", association_line2=""),
                        line_items=[(product, 1)],
                    )

        self.assertEqual(order.destination_country, "France")
        self.assertEqual(order.destination_address, "1 Rue Test\n75001 Paris")

    def test_create_public_order_supports_missing_optional_form_fields(self):
        contact = Contact.objects.create(name="Association Minimal", is_active=True)
        product = Product.objects.create(
            sku="P-ORDER-MIN",
            name="Produit Min",
            qr_code_image="qr_codes/test.png",
        )
        form_data = {
            "association_name": "Association Minimal",
            "association_line1": "3 Rue Minimal",
            "association_postal_code": "13001",
            "association_city": "Marseille",
        }

        with mock.patch(
            "wms.public_order_handlers.upsert_public_order_contact",
            return_value=contact,
        ):
            with mock.patch("wms.public_order_handlers.create_shipment_for_order"):
                with mock.patch("wms.public_order_handlers.reserve_stock_for_order"):
                    order, _ = create_public_order(
                        link=self.link,
                        form_data=form_data,
                        line_items=[(product, 1)],
                    )

        self.assertEqual(order.destination_country, "France")
        self.assertEqual(order.destination_address, "3 Rue Minimal\n13001 Marseille")
        self.assertEqual(order.notes, "")

    def test_send_public_order_notifications_adds_warning_when_confirmation_queue_fails(self):
        request = self._request_with_messages()
        contact = Contact.objects.create(
            name="Association Warn",
            email="warn@example.com",
            phone="0600000000",
        )
        order = Order.objects.create(
            public_link=self.link,
            recipient_contact=contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=contact.name,
            destination_address="1 Rue Test\n75001 Paris\nFrance",
            destination_country="France",
        )
        form_data = self._form_data(
            association_name=contact.name,
            association_email=contact.email,
            association_phone=contact.phone,
        )

        with mock.patch(
            "wms.public_order_handlers.build_public_base_url",
            return_value="https://public.example.org",
        ):
            with mock.patch(
                "wms.public_order_handlers.get_order_admin_emails",
                return_value=["admin@example.com"],
            ):
                with mock.patch(
                    "wms.public_order_handlers.render_to_string",
                    side_effect=["confirmation-body", "admin-body"],
                ):
                    with mock.patch(
                        "wms.public_order_handlers.enqueue_email_safe",
                        side_effect=[True, False],
                    ) as enqueue_mock:
                        send_public_order_notifications(
                            request=request,
                            token=self.link.token,
                            order=order,
                            form_data=form_data,
                            contact=contact,
                        )

        self.assertEqual(enqueue_mock.call_count, 2)
        warning_messages = [message.message for message in get_messages(request)]
        self.assertIn(
            "Commande envoyée, mais la confirmation email n'a pas pu être planifiée.",
            warning_messages,
        )

    def test_send_public_order_notifications_falls_back_to_contact_data(self):
        request = self._request_with_messages()
        contact = Contact.objects.create(
            name="Association Fallback",
            email="fallback@example.com",
            phone="0700000000",
        )
        order = Order.objects.create(
            public_link=self.link,
            recipient_contact=contact,
            shipper_name="Aviation Sans Frontieres",
            recipient_name=contact.name,
            destination_address="1 Rue Test\n75001 Paris\nFrance",
            destination_country="France",
        )
        form_data = {"association_name": contact.name}

        with mock.patch(
            "wms.public_order_handlers.build_public_base_url",
            return_value="https://public.example.org",
        ):
            with mock.patch(
                "wms.public_order_handlers.get_order_admin_emails",
                return_value=["admin@example.com"],
            ):
                with mock.patch(
                    "wms.public_order_handlers.render_to_string",
                    side_effect=["confirmation-body", "admin-body"],
                ) as render_mock:
                    with mock.patch(
                        "wms.public_order_handlers.enqueue_email_safe",
                        side_effect=[True, True],
                    ) as enqueue_mock:
                        send_public_order_notifications(
                            request=request,
                            token=self.link.token,
                            order=order,
                            form_data=form_data,
                            contact=contact,
                        )

        admin_context = render_mock.call_args_list[1].args[1]
        self.assertEqual(admin_context["email"], contact.email)
        self.assertEqual(admin_context["phone"], contact.phone)
        self.assertEqual(enqueue_mock.call_args_list[1].kwargs["recipient"], contact.email)
