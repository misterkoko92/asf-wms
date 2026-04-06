from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonItem,
    Destination,
    Location,
    Product,
    ProductKitItem,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    Warehouse,
)
from wms.preparation.candidates import (
    build_asf_stock_carton_candidates,
    build_deposited_carton_candidates,
    build_mixed_carton_candidates,
)


class PreparationCandidateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-candidates@example.com",
            email="prep-candidates@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.shipper_contact = Contact.objects.create(
            name="Association Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_contact,
            default_contact=Contact.objects.create(
                first_name="Alice",
                last_name="Source",
                email="alice.source@example.com",
                organization=self.shipper_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status="validated",
        )
        self.recipient_contact = Contact.objects.create(
            name="Association Destinataire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Corinne",
            last_name="Dest",
            email="corinne.dest@example.com",
            organization=self.recipient_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent,
        )
        self.recipient = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_contact,
            destination=self.destination,
            validation_status="validated",
        )
        self.other_recipient_contact = Contact.objects.create(
            name="Other Recipient",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.other_recipient = ShipmentRecipientOrganization.objects.create(
            organization=self.other_recipient_contact,
            destination=self.destination,
            validation_status="validated",
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-CAND")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            name="Kit Hygiene",
            default_location=self.location,
        )
        self.component = Product.objects.create(
            name="Compresses",
            default_location=self.location,
        )
        self.kit = Product.objects.create(
            name="Kit Maternite",
            default_location=self.location,
        )
        ProductKitItem.objects.create(kit=self.kit, component=self.component, quantity=2)
        self.deposit_lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=20,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 6, 1),
        )
        self.kit_lot = ProductLot.objects.create(
            product=self.kit,
            location=self.location,
            quantity_on_hand=5,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )

    def _create_deposit_carton(self, *, recipient_contact, code):
        shipment = Shipment.objects.create(
            reference=f"EXP-{code}",
            status=ShipmentStatus.PICKING,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=recipient_contact.name,
            recipient_contact_ref=recipient_contact,
            destination=self.destination,
            destination_address="Airport road",
            destination_country="CI",
            created_by=self.user,
        )
        carton = Carton.objects.create(
            code=code,
            shipment=shipment,
            current_location=self.location,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=self.deposit_lot,
            quantity=3,
        )
        return carton

    def test_deposited_cartons_are_read_only_from_exact_scope(self):
        matching = self._create_deposit_carton(
            recipient_contact=self.recipient_contact,
            code="CARTON-MATCH",
        )
        self._create_deposit_carton(
            recipient_contact=self.other_recipient_contact,
            code="CARTON-OTHER",
        )

        candidates = build_deposited_carton_candidates(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
        )

        self.assertEqual([candidate.carton.id for candidate in candidates], [matching.id])

    def test_asf_stock_candidates_are_mono_product(self):
        candidates = build_asf_stock_carton_candidates(product=self.product)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].product, self.product)
        self.assertEqual(candidates[0].products[0]["product"], self.product)
        self.assertEqual(len(candidates[0].products), 1)

    def test_kit_candidates_are_allowed_as_mono_product(self):
        candidates = build_asf_stock_carton_candidates(product=self.kit)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].product, self.kit)
        self.assertEqual(candidates[0].products[0]["product"], self.kit)

    def test_mixed_candidates_can_include_deposit_and_asf_stock(self):
        matching = self._create_deposit_carton(
            recipient_contact=self.recipient_contact,
            code="CARTON-MIXED",
        )
        deposited = build_deposited_carton_candidates(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
        )
        stock = build_asf_stock_carton_candidates(product=self.product)

        mixed = build_mixed_carton_candidates(
            deposited_candidates=deposited,
            stock_candidates=stock,
        )

        self.assertEqual({candidate.source for candidate in mixed}, {"deposit", "asf_stock"})
        self.assertIn(matching.id, {candidate.carton.id for candidate in mixed if candidate.carton})
