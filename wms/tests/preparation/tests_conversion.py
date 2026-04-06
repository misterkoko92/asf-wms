from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonItem,
    CartonStatus,
    Destination,
    Location,
    PreparationCartonProposal,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationReservation,
    PreparationReservationStatus,
    PreparationRun,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentValidationStatus,
    Warehouse,
)
from wms.preparation.reservations import (
    release_carton_proposal_reservations,
    reserve_stock_for_carton_proposal,
)


class PreparationConversionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-convert@example.com",
            email="prep-convert@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin conversion",
            created_by=self.user,
        )
        self.shipper_contact = Contact.objects.create(
            name="Association Source",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.shipper_default_contact = Contact.objects.create(
            first_name="Alice",
            last_name="Source",
            email="alice.source@example.com",
            organization=self.shipper_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.shipper = ShipmentShipper.objects.create(
            organization=self.shipper_contact,
            default_contact=self.shipper_default_contact,
            validation_status=ShipmentValidationStatus.VALIDATED,
        )
        self.recipient_contact = Contact.objects.create(
            name="Association Destinataire",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient_default_contact = Contact.objects.create(
            first_name="Rita",
            last_name="Dest",
            email="rita.dest@example.com",
            organization=self.recipient_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Corinne",
            last_name="Escale",
            email="correspondent@example.com",
            organization=self.recipient_contact,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ",
            country="CI",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_contact,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.shipper_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            is_active=True,
        )
        self.recipient_runtime_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=self.recipient_default_contact,
            is_active=True,
        )
        ShipmentAuthorizedRecipientContact.objects.create(
            link=self.shipper_link,
            recipient_contact=self.recipient_runtime_contact,
            is_default=True,
            is_active=True,
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=20,
            target_shipment_count=2,
            target_shipment_size_units=10,
            min_shipment_size_units=1,
            max_shipment_size_units=10,
            flight_window_start=date(2026, 5, 18),
            flight_window_end=date(2026, 5, 24),
            status=PreparationRunStatus.FROZEN,
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-PREP-CONV")
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
        self.earlier_lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=4,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 6, 1),
        )
        self.later_lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=6,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )

    def _create_proposal(self, *, source, status=PreparationShipmentProposalStatus.ACCEPTED):
        return PreparationShipmentProposal.objects.create(
            run=self.run,
            shipper=self.shipper,
            recipient_organization=self.recipient_organization,
            destination=self.destination,
            sequence=1,
            source=source,
            status=status,
            equivalent_units_total=5,
        )

    def test_conversion_creates_picking_shipment_and_consumes_reserved_stock(self):
        from wms.preparation.conversion import convert_preparation_run

        proposal = self._create_proposal(source=PreparationProposalSource.ASF_STOCK)
        carton_proposal = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.ACCEPTED,
            quantity=5,
            equivalent_units_total=5,
        )
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=proposal,
            carton_proposal=carton_proposal,
            created_by=self.user,
        )

        created_shipments = convert_preparation_run(run=self.run, created_by=self.user)

        self.assertEqual(len(created_shipments), 1)
        proposal.refresh_from_db()
        carton_proposal.refresh_from_db()
        self.run.refresh_from_db()
        shipment = proposal.converted_shipment
        carton = carton_proposal.converted_carton
        self.earlier_lot.refresh_from_db()
        self.later_lot.refresh_from_db()

        self.assertIsNotNone(shipment)
        self.assertEqual(shipment.status, ShipmentStatus.PICKING)
        self.assertEqual(shipment.destination_id, self.destination.id)
        self.assertEqual(carton.shipment_id, shipment.id)
        self.assertEqual(carton.status, CartonStatus.ASSIGNED)
        self.assertEqual(
            list(
                carton.cartonitem_set.order_by("product_lot__expires_on").values_list(
                    "quantity", flat=True
                )
            ),
            [4, 1],
        )
        self.assertEqual(
            list(
                PreparationReservation.objects.filter(carton_proposal=carton_proposal)
                .order_by("id")
                .values_list("status", flat=True)
            ),
            [PreparationReservationStatus.CONSUMED, PreparationReservationStatus.CONSUMED],
        )
        self.assertEqual(self.earlier_lot.quantity_on_hand, 0)
        self.assertEqual(self.earlier_lot.quantity_reserved, 0)
        self.assertEqual(self.later_lot.quantity_on_hand, 5)
        self.assertEqual(self.later_lot.quantity_reserved, 0)
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(carton_proposal.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(self.run.status, PreparationRunStatus.CONVERTED)

    def test_conversion_reassigns_accepted_deposit_carton_and_resyncs_source_shipment(self):
        from wms.preparation.conversion import convert_preparation_run

        source_shipment = Shipment.objects.create(
            status=ShipmentStatus.PACKED,
            shipper_name=self.shipper_default_contact.name,
            shipper_contact_ref=self.shipper_default_contact,
            recipient_name=self.recipient_default_contact.name,
            recipient_contact_ref=self.recipient_default_contact,
            correspondent_name=self.correspondent.name,
            correspondent_contact_ref=self.correspondent,
            destination=self.destination,
            destination_address=str(self.destination),
            destination_country=self.destination.country,
            created_by=self.user,
        )
        source_carton = Carton.objects.create(
            code="DEP-001",
            shipment=source_shipment,
            status=CartonStatus.PACKED,
        )
        CartonItem.objects.create(
            carton=source_carton,
            product_lot=self.earlier_lot,
            quantity=3,
        )
        proposal = self._create_proposal(source=PreparationProposalSource.DEPOSIT)
        carton_proposal = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.DEPOSIT,
            status=PreparationShipmentProposalStatus.ACCEPTED,
            quantity=3,
            equivalent_units_total=3,
            rationale={
                "source_carton_id": source_carton.id,
                "source_shipment_id": source_shipment.id,
            },
        )

        created_shipments = convert_preparation_run(run=self.run, created_by=self.user)

        self.assertEqual(len(created_shipments), 1)
        proposal.refresh_from_db()
        carton_proposal.refresh_from_db()
        source_shipment.refresh_from_db()
        source_carton.refresh_from_db()
        shipment = proposal.converted_shipment

        self.assertIsNotNone(shipment)
        self.assertNotEqual(shipment.id, source_shipment.id)
        self.assertEqual(shipment.status, ShipmentStatus.PICKING)
        self.assertEqual(source_carton.shipment_id, shipment.id)
        self.assertEqual(source_carton.status, CartonStatus.ASSIGNED)
        self.assertEqual(source_shipment.status, ShipmentStatus.DRAFT)
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(carton_proposal.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(carton_proposal.converted_carton_id, source_carton.id)

    def test_conversion_creates_only_accepted_cartons_from_partial_proposal(self):
        from wms.preparation.conversion import convert_preparation_run

        proposal = self._create_proposal(
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PARTIAL,
        )
        accepted_carton = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.ACCEPTED,
            quantity=2,
            equivalent_units_total=2,
        )
        rejected_carton = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.REJECTED,
            quantity=3,
            equivalent_units_total=3,
        )
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=proposal,
            carton_proposal=accepted_carton,
            created_by=self.user,
        )
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=proposal,
            carton_proposal=rejected_carton,
            created_by=self.user,
        )
        release_carton_proposal_reservations(carton_proposal=rejected_carton)

        created_shipments = convert_preparation_run(run=self.run, created_by=self.user)

        self.assertEqual(len(created_shipments), 1)
        proposal.refresh_from_db()
        accepted_carton.refresh_from_db()
        rejected_carton.refresh_from_db()
        shipment = proposal.converted_shipment

        self.assertIsNotNone(shipment)
        self.assertEqual(shipment.carton_set.count(), 1)
        self.assertEqual(accepted_carton.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(rejected_carton.status, PreparationShipmentProposalStatus.REJECTED)
        self.assertIsNone(rejected_carton.converted_carton_id)
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.CONVERTED)
