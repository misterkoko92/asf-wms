from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.domain.stock import StockError
from wms.models import (
    Destination,
    Location,
    PreparationCartonProposal,
    PreparationDecisionAction,
    PreparationDecisionLog,
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
    ShipmentRecipientOrganization,
    ShipmentShipper,
    Warehouse,
)
from wms.preparation.reservations import (
    compute_run_usable_stock,
    consume_carton_proposal_reservations,
    reclaim_carton_proposal_stock_for_urgency,
    release_carton_proposal_reservations,
    reserve_stock_for_carton_proposal,
)


class PreparationReservationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-res@example.com",
            email="prep-res@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W17",
            created_by=self.user,
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
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=20,
            target_shipment_count=2,
            target_shipment_size_units=10,
            flight_window_start=date(2026, 4, 20),
            flight_window_end=date(2026, 4, 27),
            status=PreparationRunStatus.DRAFT,
        )
        self.shipment_proposal = PreparationShipmentProposal.objects.create(
            run=self.run,
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            sequence=1,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            equivalent_units_total=5,
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-PREP-RES")
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
        self.carton_proposal = PreparationCartonProposal.objects.create(
            shipment_proposal=self.shipment_proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=5,
        )
        self.earlier_lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=4,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 5, 1),
        )
        self.later_lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=6,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 6, 1),
        )

    def test_reserve_stock_for_carton_proposal_uses_fefo_and_marks_lots_reserved(self):
        reservations = reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=self.shipment_proposal,
            carton_proposal=self.carton_proposal,
            created_by=self.user,
        )

        self.earlier_lot.refresh_from_db()
        self.later_lot.refresh_from_db()

        self.assertEqual([reservation.quantity for reservation in reservations], [4, 1])
        self.assertEqual(self.earlier_lot.quantity_reserved, 4)
        self.assertEqual(self.later_lot.quantity_reserved, 1)

    def test_release_carton_proposal_reservations_releases_lot_quantities(self):
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=self.shipment_proposal,
            carton_proposal=self.carton_proposal,
            created_by=self.user,
        )

        release_carton_proposal_reservations(carton_proposal=self.carton_proposal)

        self.earlier_lot.refresh_from_db()
        self.later_lot.refresh_from_db()
        statuses = list(
            PreparationReservation.objects.filter(carton_proposal=self.carton_proposal)
            .order_by("id")
            .values_list("status", flat=True)
        )

        self.assertEqual(self.earlier_lot.quantity_reserved, 0)
        self.assertEqual(self.later_lot.quantity_reserved, 0)
        self.assertEqual(statuses, [PreparationReservationStatus.RELEASED] * 2)

    def test_consume_carton_proposal_reservations_consumes_reserved_quantities(self):
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=self.shipment_proposal,
            carton_proposal=self.carton_proposal,
            created_by=self.user,
        )

        consume_carton_proposal_reservations(carton_proposal=self.carton_proposal)

        self.earlier_lot.refresh_from_db()
        self.later_lot.refresh_from_db()
        statuses = list(
            PreparationReservation.objects.filter(carton_proposal=self.carton_proposal)
            .order_by("id")
            .values_list("status", flat=True)
        )

        self.assertEqual(self.earlier_lot.quantity_on_hand, 0)
        self.assertEqual(self.earlier_lot.quantity_reserved, 0)
        self.assertEqual(self.later_lot.quantity_on_hand, 5)
        self.assertEqual(self.later_lot.quantity_reserved, 0)
        self.assertEqual(statuses, [PreparationReservationStatus.CONSUMED] * 2)

    def test_reclaim_for_urgency_releases_reserved_stock_and_marks_recalc(self):
        reserve_stock_for_carton_proposal(
            run=self.run,
            shipment_proposal=self.shipment_proposal,
            carton_proposal=self.carton_proposal,
            created_by=self.user,
        )

        reclaim_carton_proposal_stock_for_urgency(
            carton_proposal=self.carton_proposal,
            quantity=2,
            created_by=self.user,
            note="Urgence terrain",
        )

        self.shipment_proposal.refresh_from_db()
        self.carton_proposal.refresh_from_db()
        self.earlier_lot.refresh_from_db()
        decision = PreparationDecisionLog.objects.get(
            carton_proposal=self.carton_proposal,
            action=PreparationDecisionAction.RECLAIM_FOR_URGENCY,
        )

        self.assertEqual(
            self.shipment_proposal.status, PreparationShipmentProposalStatus.NEEDS_RECALC
        )
        self.assertEqual(
            self.carton_proposal.status, PreparationShipmentProposalStatus.NEEDS_RECALC
        )
        self.assertEqual(self.earlier_lot.quantity_reserved, 2)
        self.assertEqual(decision.note, "Urgence terrain")

    def test_manual_reserve_reduces_run_usable_stock_and_can_block_reservation(self):
        usable = compute_run_usable_stock(product=self.product, manual_reserve_quantity=3)

        self.assertEqual(usable, 7)

        with self.assertRaises(StockError):
            reserve_stock_for_carton_proposal(
                run=self.run,
                shipment_proposal=self.shipment_proposal,
                carton_proposal=self.carton_proposal,
                created_by=self.user,
                manual_reserve_quantity=6,
            )
