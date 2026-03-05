from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.domain.orders import create_shipment_for_order
from wms.domain.stock import StockError
from wms.models import (
    Destination,
    Order,
    OrderLine,
    OrderStatus,
    OrganizationRole,
    OrganizationRoleAssignment,
    Product,
    RecipientBinding,
    ShipperScope,
    WmsRuntimeSettings,
)


class DomainOrdersOrgRolesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="domain-org-roles",
            password="pass1234",
        )
        self.product = Product.objects.create(
            sku="ORG-ROLE-001",
            name="Org Role Product",
            qr_code_image="qr_codes/test.png",
        )
        runtime = WmsRuntimeSettings.get_solo()
        runtime.org_roles_engine_enabled = True
        runtime.save(update_fields=["org_roles_engine_enabled"])

    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_org(f"Correspondent {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _build_order(self, *, shipper, recipient, destination):
        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=shipper.name,
            shipper_contact=shipper,
            recipient_name=recipient.name,
            recipient_contact=recipient,
            correspondent_name="",
            destination_address="Legacy destination",
            destination_city=destination.city,
            destination_country=destination.country,
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=self.product, quantity=1)
        return order

    def test_create_shipment_for_order_uses_recipient_binding_when_engine_enabled(self):
        destination = self._create_destination("BKO")
        shipper = self._create_org("Shipper BKO")
        recipient = self._create_org("Recipient BKO")

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=True,
        )

        order = self._build_order(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )

        shipment = create_shipment_for_order(order=order)

        self.assertEqual(shipment.shipper_contact_ref_id, shipper.id)
        self.assertEqual(shipment.recipient_contact_ref_id, recipient.id)
        self.assertEqual(shipment.destination_id, destination.id)

    def test_create_shipment_for_order_blocks_unbound_recipient_when_engine_enabled(self):
        destination = self._create_destination("DLA")
        shipper = self._create_org("Shipper DLA")
        recipient = self._create_org("Recipient DLA")

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        order = self._build_order(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )

        with self.assertRaisesMessage(StockError, "Destinataire non autorise"):
            create_shipment_for_order(order=order)
