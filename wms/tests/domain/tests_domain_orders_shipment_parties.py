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
    Product,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
)


class DomainOrdersShipmentPartiesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="domain-shipment-parties",
            password="pass1234",  # pragma: allowlist secret
        )
        self.product = Product.objects.create(
            sku="SHIPMENT-PARTY-001",
            name="Shipment Party Product",
            qr_code_image="qr_codes/test.png",
        )

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

    def _create_person(self, name: str, *, organization: Contact) -> Contact:
        first_name, last_name = name.split(" ", 1)
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name,
            organization=organization,
            is_active=True,
        )

    def _create_shipper_record(
        self,
        organization: Contact,
        *,
        can_send_to_all: bool = False,
    ) -> ShipmentShipper:
        default_contact = self._create_person(
            f"Default {organization.name}",
            organization=organization,
        )
        return ShipmentShipper.objects.create(
            organization=organization,
            default_contact=default_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            can_send_to_all=can_send_to_all,
            is_active=True,
        )

    def _create_recipient_record(
        self,
        *,
        organization: Contact,
        destination: Destination,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
    ) -> ShipmentRecipientOrganization:
        return ShipmentRecipientOrganization.objects.create(
            organization=organization,
            destination=destination,
            validation_status=validation_status,
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

    def test_create_shipment_for_order_uses_shipment_party_link(self):
        destination = self._create_destination("BKO")
        shipper = self._create_org("Shipper BKO")
        recipient = self._create_org("Recipient BKO")

        shipper_record = self._create_shipper_record(shipper)
        recipient_record = self._create_recipient_record(
            organization=recipient,
            destination=destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper_record,
            recipient_organization=recipient_record,
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

    def test_create_shipment_for_order_normalizes_person_contacts_to_shipment_parties(self):
        destination = self._create_destination("RUN")
        shipper_org = self._create_org("Shipper Org RUN")
        recipient_org = self._create_org("Recipient Org RUN")
        shipper_person = self._create_person("Sam Shipper", organization=shipper_org)
        recipient_person = self._create_person("Ana Recipient", organization=recipient_org)

        shipper_record = self._create_shipper_record(shipper_org)
        recipient_record = self._create_recipient_record(
            organization=recipient_org,
            destination=destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper_record,
            recipient_organization=recipient_record,
            is_active=True,
        )

        order = self._build_order(
            shipper=shipper_person,
            recipient=recipient_person,
            destination=destination,
        )

        shipment = create_shipment_for_order(order=order)

        self.assertEqual(shipment.shipper_contact_ref_id, shipper_person.id)
        self.assertEqual(shipment.recipient_contact_ref_id, recipient_person.id)
        self.assertEqual(shipment.destination_id, destination.id)

    def test_create_shipment_for_order_blocks_unlinked_recipient(self):
        destination = self._create_destination("DLA")
        shipper = self._create_org("Shipper DLA")
        recipient = self._create_org("Recipient DLA")
        allowed_recipient = self._create_org("Allowed Recipient DLA")

        shipper_record = self._create_shipper_record(shipper)
        self._create_recipient_record(
            organization=recipient,
            destination=destination,
        )
        allowed_recipient_record = self._create_recipient_record(
            organization=allowed_recipient,
            destination=destination,
        )
        ShipmentShipperRecipientLink.objects.create(
            shipper=shipper_record,
            recipient_organization=allowed_recipient_record,
            is_active=True,
        )

        order = self._build_order(
            shipper=shipper,
            recipient=recipient,
            destination=destination,
        )

        with self.assertRaisesMessage(StockError, "Destinataire non autorise"):
            create_shipment_for_order(order=order)
