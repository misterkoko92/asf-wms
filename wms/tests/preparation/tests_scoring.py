from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    CartonItem,
    Destination,
    Location,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationRun,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    Warehouse,
)
from wms.preparation.scoring import (
    compute_fairness_history_quantity,
    compute_remaining_need,
    score_preparation_candidate,
)


class PreparationScoringTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-scoring@example.com",
            email="prep-scoring@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W18",
            created_by=self.user,
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=40,
            target_shipment_count=4,
            target_shipment_size_units=10,
            flight_window_start=date(2026, 4, 27),
            flight_window_end=date(2026, 5, 4),
            status=PreparationRunStatus.DRAFT,
        )
        self.destination_contact = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Corinne",
            last_name="Dest",
            email="corinne.dest@example.com",
            organization=self.destination_contact,
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
            organization=self.destination_contact,
            destination=self.destination,
            validation_status="validated",
        )
        self.association_contact = Contact.objects.create(
            name="Association A",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.association_shipper = ShipmentShipper.objects.create(
            organization=self.association_contact,
            default_contact=Contact.objects.create(
                first_name="Alice",
                last_name="Association",
                email="alice.association@example.com",
                organization=self.association_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status="validated",
        )
        self.asf_contact = Contact.objects.create(
            name="ASF",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.asf_shipper = ShipmentShipper.objects.create(
            organization=self.asf_contact,
            default_contact=Contact.objects.create(
                first_name="Ana",
                last_name="ASF",
                email="ana.asf@example.com",
                organization=self.asf_contact,
                contact_type=ContactType.PERSON,
                is_active=True,
            ),
            validation_status="validated",
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-SCORE")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.category_l2 = ProductCategory.objects.create(name="Kits")
        self.category_l3 = ProductCategory.objects.create(
            name="Obstetrique",
            parent=self.category_l2,
        )
        self.requested_product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category_l3,
            default_location=self.location,
        )
        self.allowed_product = Product.objects.create(
            name="Kit Hygiene",
            category=self.category_l3,
            default_location=self.location,
        )
        self.lot_requested = ProductLot.objects.create(
            product=self.requested_product,
            location=self.location,
            quantity_on_hand=50,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )
        self.lot_allowed = ProductLot.objects.create(
            product=self.allowed_product,
            location=self.location,
            quantity_on_hand=50,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.requested_product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=10,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.allowed_product,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=10,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )

    def _create_history_shipment(
        self, *, shipper_contact, product_lot, quantity, status, source=None
    ):
        shipment = Shipment.objects.create(
            reference=f"EXP-{shipper_contact.id}-{status}-{quantity}-{product_lot.id}",
            status=status,
            shipper_name=shipper_contact.name,
            shipper_contact_ref=shipper_contact,
            recipient_name=self.destination_contact.name,
            recipient_contact_ref=self.destination_contact,
            destination=self.destination,
            destination_address="Airport road",
            destination_country="CI",
            created_by=self.user,
        )
        carton = Carton.objects.create(
            code=f"CARTON-{shipment.reference}",
            shipment=shipment,
            current_location=self.location,
        )
        CartonItem.objects.create(
            carton=carton,
            product_lot=product_lot,
            quantity=quantity,
        )
        if source is not None:
            PreparationShipmentProposal.objects.create(
                run=self.run,
                shipper=self.association_shipper,
                recipient_organization=self.recipient,
                destination=self.destination,
                sequence=shipment.id,
                source=source,
                status=PreparationShipmentProposalStatus.CONVERTED,
                equivalent_units_total=quantity,
                converted_shipment=shipment,
            )
        return shipment

    def test_requested_scores_above_allowed(self):
        requested_score = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.requested_product,
            asf_shipper=self.asf_shipper,
        )
        allowed_score = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.allowed_product,
            asf_shipper=self.asf_shipper,
        )

        self.assertGreater(requested_score.score, allowed_score.score)

    def test_unspecified_is_excluded_by_default_but_can_be_enabled(self):
        unspecified_product = Product.objects.create(
            name="Produit Libre",
            category=self.category_l3,
            default_location=self.location,
        )

        excluded = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=unspecified_product,
            asf_shipper=self.asf_shipper,
        )
        included = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=unspecified_product,
            asf_shipper=self.asf_shipper,
            include_unspecified=True,
        )

        self.assertTrue(excluded.excluded)
        self.assertFalse(included.excluded)

    def test_remaining_need_deducts_all_relevant_packed_and_planned_shipments(self):
        self._create_history_shipment(
            shipper_contact=self.association_contact,
            product_lot=self.lot_requested,
            quantity=3,
            status=ShipmentStatus.PACKED,
        )
        self._create_history_shipment(
            shipper_contact=self.association_contact,
            product_lot=self.lot_requested,
            quantity=2,
            status=ShipmentStatus.PLANNED,
        )

        remaining = compute_remaining_need(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.requested_product,
            target_equivalent_units=10,
        )

        self.assertEqual(remaining, 5)

    def test_fairness_uses_only_asf_stock_or_mixed_history(self):
        self._create_history_shipment(
            shipper_contact=self.association_contact,
            product_lot=self.lot_requested,
            quantity=4,
            status=ShipmentStatus.PACKED,
            source=PreparationProposalSource.ASF_STOCK,
        )
        self._create_history_shipment(
            shipper_contact=self.association_contact,
            product_lot=self.lot_requested,
            quantity=6,
            status=ShipmentStatus.PACKED,
            source=PreparationProposalSource.DEPOSIT,
        )

        fairness = compute_fairness_history_quantity(
            destination=self.destination,
            product=self.requested_product,
        )

        self.assertEqual(fairness, 4)

    def test_non_asf_shipper_beats_asf_with_equal_conditions(self):
        association_score = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.requested_product,
            asf_shipper=self.asf_shipper,
            asf_penalty=0.85,
        )
        asf_score = score_preparation_candidate(
            shipper=self.asf_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.requested_product,
            asf_shipper=self.asf_shipper,
            asf_penalty=0.85,
        )

        self.assertGreater(association_score.score, asf_score.score)

    def test_refused_preferences_are_excluded_and_fairness_penalty_is_explained(self):
        refused_product = Product.objects.create(
            name="Produit Refuse",
            default_location=self.location,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=refused_product,
            status=RecipientProductPreferenceStatus.REFUSED,
            created_by=self.user,
        )

        refused_score = score_preparation_candidate(
            shipper=self.association_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=refused_product,
            asf_shipper=self.asf_shipper,
        )
        self._create_history_shipment(
            shipper_contact=self.association_contact,
            product_lot=self.lot_requested,
            quantity=4,
            status=ShipmentStatus.PACKED,
            source=PreparationProposalSource.ASF_STOCK,
        )

        requested_score = score_preparation_candidate(
            shipper=self.asf_shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            product=self.requested_product,
            asf_shipper=self.asf_shipper,
            asf_penalty=0.9,
            fairness_category_level="L3",
        )

        self.assertTrue(refused_score.excluded)
        self.assertEqual(refused_score.reasons, ["refused preference"])
        self.assertEqual(
            compute_fairness_history_quantity(
                destination=self.destination,
                product=refused_product,
            ),
            0,
        )
        self.assertIn("fairness penalty 4", requested_score.reasons)
        self.assertIn("asf penalty 0.9", requested_score.reasons)
