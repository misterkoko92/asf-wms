import contextlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.portal_order_handlers import create_portal_order


class PortalOrderHandlersTests(SimpleTestCase):
    def test_create_portal_order_creates_order_lines_and_triggers_services(self):
        profile = SimpleNamespace(
            contact=SimpleNamespace(name="Association Contact"),
        )
        user = SimpleNamespace(id=1)
        product_a = SimpleNamespace(id=11)
        product_b = SimpleNamespace(id=12)
        order = SimpleNamespace(
            lines=SimpleNamespace(
                create=mock.Mock(),
                exists=mock.Mock(return_value=False),
                all=mock.Mock(return_value=[]),
            )
        )

        with mock.patch(
            "wms.portal_order_handlers.Order.objects.create",
            return_value=order,
        ) as create_mock:
            with mock.patch(
                "wms.portal_order_handlers.transaction.atomic",
                return_value=contextlib.nullcontext(),
            ):
                with mock.patch("wms.portal_order_handlers.create_shipment_for_order") as shipment_mock:
                    with mock.patch("wms.portal_order_handlers.reserve_stock_for_order") as reserve_mock:
                        created = create_portal_order(
                            user=user,
                            profile=profile,
                            recipient_name="Recipient",
                            recipient_contact="recipient-contact",
                            destination_address="1 Rue Test",
                            destination_city="Paris",
                            destination_country="",
                            notes="note",
                            line_items=[(product_a, 2), (product_b, 3)],
                        )

        self.assertIs(created, order)
        create_mock.assert_called_once_with(
            reference="",
            status=mock.ANY,
            association_contact=profile.contact,
            shipper_name="Association Contact",
            shipper_contact=profile.contact,
            recipient_name="Recipient",
            recipient_contact="recipient-contact",
            destination_address="1 Rue Test",
            destination_city="Paris",
            destination_country="France",
            created_by=user,
            notes="note",
        )
        self.assertEqual(order.lines.create.call_count, 2)
        shipment_mock.assert_called_once_with(order=order)
        reserve_mock.assert_called_once_with(order=order)

    def test_create_portal_order_keeps_explicit_destination_country(self):
        profile = SimpleNamespace(
            contact=SimpleNamespace(name="Association Contact"),
        )
        user = SimpleNamespace(id=1)
        order = SimpleNamespace(
            lines=SimpleNamespace(
                create=mock.Mock(),
                exists=mock.Mock(return_value=False),
                all=mock.Mock(return_value=[]),
            )
        )

        with mock.patch("wms.portal_order_handlers.Order.objects.create", return_value=order) as create_mock:
            with mock.patch(
                "wms.portal_order_handlers.transaction.atomic",
                return_value=contextlib.nullcontext(),
            ):
                with mock.patch("wms.portal_order_handlers.create_shipment_for_order"):
                    with mock.patch("wms.portal_order_handlers.reserve_stock_for_order"):
                        create_portal_order(
                            user=user,
                            profile=profile,
                            recipient_name="Recipient",
                            recipient_contact="recipient-contact",
                            destination_address="1 Rue Test",
                            destination_city="Paris",
                            destination_country="Belgique",
                            notes="",
                            line_items=[],
                        )

        self.assertEqual(create_mock.call_args.kwargs["destination_country"], "Belgique")
