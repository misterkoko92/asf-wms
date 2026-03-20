from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.import_services import import_product_row
from wms.models import (
    Carton,
    CartonFormat,
    Destination,
    Order,
    OrderLine,
    OrderStatus,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipperScope,
)
from wms.services import prepare_order, reserve_stock_for_order


class FlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="flow-user", password="pass1234")

    def _create_contact(self, name, *, contact_type=ContactType.ORGANIZATION):
        return Contact.objects.create(name=name, contact_type=contact_type, is_active=True)

    def _assign_role(self, contact, role):
        assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
            organization=contact,
            role=role,
            defaults={"is_active": True},
        )
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=["is_active", "updated_at"])
        return assignment

    def test_import_to_order_prepare_flow(self):
        row = {
            "name": "Compresses steriles",
            "sku": "CMP-1",
            "brand": "ACME",
            "warehouse": "Main",
            "zone": "A",
            "aisle": "01",
            "shelf": "001",
            "length_cm": "2",
            "width_cm": "3",
            "height_cm": "4",
            "weight_g": "50",
            "quantity": "10",
        }
        product, created, warnings = import_product_row(row, user=self.user)
        self.assertTrue(created)
        self.assertEqual(warnings, [])

        CartonFormat.objects.create(
            name="Default",
            length_cm=40,
            width_cm=30,
            height_cm=30,
            max_weight_g=8000,
            is_default=True,
        )
        correspondent = self._create_contact("Flow Correspondent", contact_type=ContactType.PERSON)
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Flow Shipper")
        shipper_contact = self._create_contact(
            "Jean Flow Shipper",
            contact_type=ContactType.PERSON,
        )
        shipper_contact.organization = shipper
        shipper_contact.save(update_fields=["organization"])
        recipient = self._create_contact("Flow Recipient")
        recipient_contact = self._create_contact(
            "Marie Flow Recipient",
            contact_type=ContactType.PERSON,
        )
        recipient_contact.organization = recipient
        recipient_contact.save(update_fields=["organization"])
        shipper_assignment = self._assign_role(shipper, OrganizationRole.SHIPPER)
        self._assign_role(recipient, OrganizationRole.RECIPIENT)
        ShipperScope.objects.create(role_assignment=shipper_assignment, destination=destination)
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
        )
        shipment_shipper = ShipmentShipper.objects.create(
            organization=shipper,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shipment_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=recipient,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=shipment_recipient_organization,
            contact=recipient_contact,
            is_active=True,
        )
        shipment_link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipment_shipper,
            recipient_organization=shipment_recipient_organization,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=shipment_link,
            recipient_contact=shipment_recipient_contact,
            is_default=True,
            is_active=True,
        )

        order = Order.objects.create(
            status=OrderStatus.DRAFT,
            shipper_name=shipper_contact.name,
            shipper_contact=shipper_contact,
            recipient_name=recipient_contact.name,
            recipient_contact=recipient_contact,
            correspondent_name=correspondent.name,
            correspondent_contact=correspondent,
            destination_address="10 Rue Test",
            destination_city=destination.city,
            destination_country="France",
            created_by=self.user,
        )
        OrderLine.objects.create(order=order, product=product, quantity=4)

        reserve_stock_for_order(order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.RESERVED)

        prepare_order(user=self.user, order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.READY)
        self.assertIsNotNone(order.shipment_id)
        self.assertTrue(Carton.objects.filter(shipment=order.shipment).exists())
