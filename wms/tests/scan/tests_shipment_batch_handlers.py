from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentValidationStatus,
)
from wms.shipment_batch_handlers import (
    ShipmentBatchValidationError,
    create_prepared_shipment_batch,
)


class PreparedShipmentBatchHandlersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shipment-batch-user",
            password="pass1234",  # pragma: allowlist secret
        )

    def _create_shipment_party_triplet(self, code):
        correspondent_org = Contact.objects.create(
            name=f"Correspondent Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent = Contact.objects.create(
            name=f"Correspondent {code}",
            contact_type=ContactType.PERSON,
            first_name="Correspondent",
            last_name=code,
            organization=correspondent_org,
            is_active=True,
        )
        destination = Destination.objects.create(
            city=f"Destination {code}",
            iata_code=code,
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.create(
            organization=correspondent_org,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_correspondent=True,
            is_active=True,
        )

        shipper_org = Contact.objects.create(
            name=f"Shipper Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_contact = Contact.objects.create(
            name=f"Shipper {code}",
            contact_type=ContactType.PERSON,
            first_name="Shipper",
            last_name=code,
            organization=shipper_org,
            is_active=True,
        )
        shipper = ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )

        recipient_org_contact = Contact.objects.create(
            name=f"Recipient Org {code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_org = ShipmentRecipientOrganization.objects.create(
            organization=recipient_org_contact,
            destination=destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        recipient_contact = Contact.objects.create(
            name=f"Recipient {code}",
            contact_type=ContactType.PERSON,
            first_name="Recipient",
            last_name=code,
            organization=recipient_org_contact,
            is_active=True,
        )
        shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=recipient_org,
            contact=recipient_contact,
            is_active=True,
        )
        link = ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_org,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=shipment_recipient_contact,
            is_default=True,
            is_active=True,
        )
        return destination, shipper_contact, recipient_contact

    def test_create_prepared_shipment_batch_creates_independent_shipments(self):
        destination_a, shipper_a, recipient_a = self._create_shipment_party_triplet("BTA")
        destination_b, shipper_b, recipient_b = self._create_shipment_party_triplet("BTB")

        result = create_prepared_shipment_batch(
            rows=[
                {
                    "destination": destination_a,
                    "shipper_contact": shipper_a,
                    "recipient_contact": recipient_a,
                    "planned_carton_count": 10,
                },
                {
                    "destination": destination_b,
                    "shipper_contact": shipper_b,
                    "recipient_contact": recipient_b,
                    "planned_carton_count": 5,
                },
            ],
            user=self.user,
        )

        self.assertEqual(len(result.shipments), 2)
        self.assertEqual(result.shipments[0].destination, destination_a)
        self.assertEqual(result.shipments[0].shipper_contact_ref, shipper_a)
        self.assertEqual(result.shipments[0].recipient_contact_ref, recipient_a)
        self.assertEqual(result.shipments[0].planned_carton_count, 10)
        self.assertEqual(result.shipments[0].status, ShipmentStatus.DRAFT)
        self.assertEqual(result.shipments[1].destination, destination_b)
        self.assertEqual(result.shipments[1].planned_carton_count, 5)
        self.assertEqual(Shipment.objects.count(), 2)

    def test_create_prepared_shipment_batch_is_all_or_nothing(self):
        destination, shipper, recipient = self._create_shipment_party_triplet("BTO")

        with self.assertRaises(ShipmentBatchValidationError):
            create_prepared_shipment_batch(
                rows=[
                    {
                        "destination": destination,
                        "shipper_contact": shipper,
                        "recipient_contact": recipient,
                        "planned_carton_count": 10,
                    },
                    {
                        "destination": destination,
                        "shipper_contact": shipper,
                        "recipient_contact": recipient,
                        "planned_carton_count": 0,
                    },
                ],
                user=self.user,
            )

        self.assertEqual(Shipment.objects.count(), 0)
