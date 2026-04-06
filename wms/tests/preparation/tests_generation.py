from datetime import UTC, date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    Carton,
    Destination,
    Flight,
    FlightSourceBatch,
    FlightSourceBatchStatus,
    Location,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationRunNeedSnapshot,
    PreparationRunStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    ProductCategory,
    ProductLot,
    ProductLotStatus,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
    RecurringPreparationNeed,
    RecurringPreparationPeriodUnit,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    Warehouse,
)
from wms.planning.flight_providers import (
    PlanningFlightProviderConfigurationError,
    PlanningFlightProviderError,
)
from wms.preparation.candidates import PreparationCandidate
from wms.preparation.generation import (
    _build_scope_specs,
    _category_is_within,
    _create_shipment_proposal,
    _destination_capacity,
    _products_from_preferences,
    _resolve_flight_batch,
    _shipment_source,
    generate_preparation_run,
)
from wms.preparation.needs import snapshot_active_recurring_needs
from wms.preparation.scoring import PreparationScoreResult


class PreparationGenerationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prep-generation@example.com",
            email="prep-generation@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin W19",
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
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-GEN")
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
        self.product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category_l3,
            default_location=self.location,
        )
        self.lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=40,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 7, 1),
        )
        self.run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.user,
            target_equivalent_units=12,
            target_shipment_count=3,
            target_shipment_size_units=10,
            min_shipment_size_units=5,
            max_shipment_size_units=12,
            flight_window_start=date(2026, 5, 4),
            flight_window_end=date(2026, 5, 10),
            status=PreparationRunStatus.DRAFT,
        )
        PreparationDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=20,
            max_usable_flights_per_week=1,
            max_equivalent_units_per_week=20,
        )
        PreparationShipperRule.objects.create(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
            mode=PreparationShipperMode.ASF_AUTO_ALLOWED,
            score_coefficient="1.00",
        )
        RecurringPreparationNeed.objects.create(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            period_unit=RecurringPreparationPeriodUnit.WEEK,
            target_equivalent_units=12,
            is_active=True,
            created_by=self.user,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=12,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )

    def _create_batch(self, *, imported_at=None, capacity_units=30):
        batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=self.run.flight_window_start,
            period_end=self.run.flight_window_end,
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=imported_at or timezone.now(),
        )
        Flight.objects.create(
            batch=batch,
            flight_number="AF702",
            departure_date=self.run.flight_window_start,
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=capacity_units,
        )
        return batch

    def _create_deposit_shipment(self, *, quantity, code="CARTON-DEPOT"):
        shipment = Shipment.objects.create(
            reference=f"EXP-{code}",
            status=ShipmentStatus.PICKING,
            shipper_name=self.shipper_contact.name,
            shipper_contact_ref=self.shipper_contact,
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
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
        carton.cartonitem_set.create(product_lot=self.lot, quantity=quantity)
        return shipment, carton

    def test_generation_snapshots_needs_and_parameters_and_creates_proposals(self):
        batch = self._create_batch(capacity_units=20)

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=lambda *, start_date, end_date: batch,
        )

        generated_run.refresh_from_db()
        proposal = generated_run.shipment_proposals.get()
        carton = proposal.carton_proposals.get()

        self.assertEqual(generated_run.status, PreparationRunStatus.GENERATED)
        self.assertEqual(PreparationRunNeedSnapshot.objects.filter(run=generated_run).count(), 1)
        self.assertEqual(proposal.equivalent_units_total, 12)
        self.assertEqual(carton.quantity, 12)
        self.assertEqual(carton.product, self.product)
        self.assertEqual(carton.reservations.count(), 1)
        self.assertEqual(
            generated_run.parameter_snapshot["inputs"]["shipper_ids"],
            [self.shipper.id],
        )
        self.assertEqual(
            generated_run.parameter_snapshot["inputs"]["destination_ids"],
            [self.destination.id],
        )
        self.assertEqual(
            generated_run.parameter_snapshot["flight_source"]["batch_id"],
            batch.id,
        )
        self.assertFalse(generated_run.parameter_snapshot["flight_source"]["used_fallback"])

    def test_generation_respects_target_size_and_backlogs_small_remainder(self):
        self.run.target_equivalent_units = 24
        self.run.target_shipment_count = 4
        self.run.target_shipment_size_units = 10
        self.run.min_shipment_size_units = 5
        self.run.max_shipment_size_units = 10
        self.run.save(
            update_fields=[
                "target_equivalent_units",
                "target_shipment_count",
                "target_shipment_size_units",
                "min_shipment_size_units",
                "max_shipment_size_units",
            ]
        )
        destination_rule = PreparationDestinationRule.objects.get(
            parameter_set=self.parameter_set,
            destination=self.destination,
        )
        destination_rule.max_equivalent_units_per_flight = 30
        destination_rule.max_equivalent_units_per_week = 30
        destination_rule.save(
            update_fields=[
                "max_equivalent_units_per_flight",
                "max_equivalent_units_per_week",
            ]
        )
        recurring_need = RecurringPreparationNeed.objects.get(
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
        )
        recurring_need.target_equivalent_units = 24
        recurring_need.save(update_fields=["target_equivalent_units"])
        preference = RecipientProductPreference.objects.get(
            recipient_organization=self.recipient,
            product=self.product,
        )
        preference.quantity_target = 24
        preference.save(update_fields=["quantity_target"])
        batch = self._create_batch(capacity_units=30)

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=lambda *, start_date, end_date: batch,
        )

        shipment_totals = list(
            generated_run.shipment_proposals.order_by("sequence").values_list(
                "equivalent_units_total",
                flat=True,
            )
        )

        self.assertEqual(shipment_totals, [10, 10])
        self.assertEqual(
            generated_run.parameter_snapshot["backlog"],
            [
                {
                    "shipper_id": self.shipper.id,
                    "recipient_organization_id": self.recipient.id,
                    "destination_id": self.destination.id,
                    "equivalent_units": 4,
                    "reason": "below_min_shipment_size",
                }
            ],
        )

    def test_generation_uses_last_exploitable_batch_on_api_failure(self):
        fallback_batch = self._create_batch(
            imported_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
            capacity_units=18,
        )

        def failing_loader(*, start_date, end_date):
            raise PlanningFlightProviderError("upstream unavailable")

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=failing_loader,
        )

        flight_source = generated_run.parameter_snapshot["flight_source"]

        self.assertEqual(flight_source["batch_id"], fallback_batch.id)
        self.assertEqual(flight_source["mode"], "fallback")
        self.assertTrue(flight_source["used_fallback"])
        self.assertEqual(flight_source["fallback_reason"], "upstream unavailable")
        self.assertEqual(flight_source["freshness_days"], 3)

    def test_generation_uses_previous_batch_pattern_when_api_is_unconfigured(self):
        self.run.flight_window_start = date(2026, 5, 12)
        self.run.flight_window_end = date(2026, 5, 18)
        self.run.save(update_fields=["flight_window_start", "flight_window_end"])
        fallback_batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=date(2026, 5, 4),
            period_end=date(2026, 5, 10),
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        )
        Flight.objects.create(
            batch=fallback_batch,
            flight_number="AF702",
            departure_date=date(2026, 5, 5),
            departure_time=time(9, 45),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=18,
        )

        def unconfigured_loader(*, start_date, end_date):
            raise PlanningFlightProviderConfigurationError("PLANNING_FLIGHT_API_KEY is required.")

        generated_run = generate_preparation_run(
            run=self.run,
            shippers=[self.shipper],
            destinations=[self.destination],
            api_batch_loader=unconfigured_loader,
        )

        flight_source = generated_run.parameter_snapshot["flight_source"]

        self.assertEqual(flight_source["batch_id"], fallback_batch.id)
        self.assertEqual(flight_source["mode"], "fallback")
        self.assertTrue(flight_source["used_fallback"])
        self.assertEqual(flight_source["fallback_reason"], "PLANNING_FLIGHT_API_KEY is required.")
        self.assertEqual(generated_run.shipment_proposals.count(), 1)

    def test_products_from_preferences_supports_exact_and_category_matches(self):
        other_product = Product.objects.create(
            name="Kit Hygiene",
            category=self.category_l3,
            default_location=self.location,
        )
        ProductLot.objects.create(
            product=other_product,
            location=self.location,
            quantity_on_hand=12,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 8, 1),
        )
        uncategorized_product = Product.objects.create(
            name="Produit Libre",
            default_location=self.location,
        )
        ProductLot.objects.create(
            product=uncategorized_product,
            location=self.location,
            quantity_on_hand=4,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
            expires_on=date(2026, 9, 1),
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            category=self.category_l2,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=6,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )
        other_recipient_contact = Contact.objects.create(
            name="Sans Preferences",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        other_recipient = ShipmentRecipientOrganization.objects.create(
            organization=other_recipient_contact,
            destination=self.destination,
            validation_status="validated",
        )

        self.assertTrue(
            _category_is_within(
                product_category=self.category_l3,
                target_category=self.category_l2,
            )
        )
        self.assertEqual(_products_from_preferences(recipient_organization=other_recipient), [])
        products = _products_from_preferences(recipient_organization=self.recipient)

        self.assertEqual(
            [product.id for product in products],
            [self.product.id, other_product.id],
        )

    def test_resolve_flight_batch_uses_generic_last_batch_and_can_raise_without_fallback(self):
        future_batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=date(2026, 5, 20),
            period_end=date(2026, 5, 26),
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=datetime(2026, 5, 19, 8, 0, tzinfo=UTC),
        )
        Flight.objects.create(
            batch=future_batch,
            flight_number="AF799",
            departure_date=date(2026, 5, 21),
            departure_time=time(11, 30),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=14,
        )

        def failing_loader(*, start_date, end_date):
            raise PlanningFlightProviderError("airfrance unavailable")

        batch, flight_source = _resolve_flight_batch(
            run=self.run,
            api_batch_loader=failing_loader,
        )

        self.assertEqual(batch.id, future_batch.id)
        self.assertEqual(flight_source["capacity_reference"], "fallback_batch_period")

        FlightSourceBatch.objects.all().delete()
        with self.assertRaises(PlanningFlightProviderError):
            _resolve_flight_batch(
                run=self.run,
                api_batch_loader=failing_loader,
            )

    def test_destination_capacity_filters_allowed_weekdays_and_caps(self):
        weekday_rule = PreparationDestinationRule.objects.get(
            parameter_set=self.parameter_set,
            destination=self.destination,
        )
        weekday_rule.allowed_weekdays = ["mon", "wed"]
        weekday_rule.max_usable_flights_per_week = 1
        weekday_rule.max_equivalent_units_per_flight = 9
        weekday_rule.max_equivalent_units_per_week = 7
        weekday_rule.max_shipments_per_week = None
        weekday_rule.save(
            update_fields=[
                "allowed_weekdays",
                "max_usable_flights_per_week",
                "max_equivalent_units_per_flight",
                "max_equivalent_units_per_week",
                "max_shipments_per_week",
            ]
        )
        batch = FlightSourceBatch.objects.create(
            source="api",
            period_start=self.run.flight_window_start,
            period_end=self.run.flight_window_end,
            status=FlightSourceBatchStatus.IMPORTED,
            imported_at=timezone.now(),
        )
        Flight.objects.create(
            batch=batch,
            flight_number="AF701",
            departure_date=date(2026, 5, 4),
            departure_time=time(9, 0),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=12,
        )
        Flight.objects.create(
            batch=batch,
            flight_number="AF702",
            departure_date=date(2026, 5, 5),
            departure_time=time(9, 0),
            destination_iata="ABJ",
            origin_iata="CDG",
            routing="CDG-ABJ",
            route_pos=1,
            destination=self.destination,
            capacity_units=12,
        )

        capacity = _destination_capacity(
            run=self.run,
            destination=self.destination,
            destination_rule=weekday_rule,
            flight_batch=batch,
        )

        self.assertEqual(capacity["usable_flight_count"], 1)
        self.assertEqual(capacity["capacity_units"], 7)
        self.assertEqual(capacity["shipment_limit"], 10**9)

    @patch("wms.preparation.generation.score_preparation_candidate")
    @patch("wms.preparation.generation.build_asf_stock_carton_candidates")
    @patch("wms.preparation.generation._products_from_preferences")
    @patch("wms.preparation.generation.build_deposited_carton_candidates")
    def test_build_scope_specs_prefers_best_deposit_product_and_adds_stock_specs(
        self,
        mock_deposited_candidates,
        mock_products_from_preferences,
        mock_stock_candidates,
        mock_score_candidate,
    ):
        alt_product = Product.objects.create(
            name="Kit Hygiene",
            category=self.category_l3,
            default_location=self.location,
        )
        shipment, carton = self._create_deposit_shipment(quantity=3)
        need_snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        deposit_candidate = PreparationCandidate(
            source="deposit",
            quantity=3,
            products=[
                {"product": self.product, "quantity": 1},
                {"product": alt_product, "quantity": 2},
            ],
            carton=carton,
            shipment=shipment,
        )
        mock_deposited_candidates.return_value = [deposit_candidate]
        mock_products_from_preferences.return_value = [self.product]
        mock_stock_candidates.return_value = [
            PreparationCandidate(
                source="asf_stock",
                quantity=9,
                products=[{"product": self.product, "quantity": 9}],
                product=self.product,
            )
        ]
        mock_score_candidate.side_effect = [
            PreparationScoreResult(
                score=0.0,
                excluded=True,
                preference_status="unspecified",
                remaining_need=0,
                fairness_quantity=0,
                reasons=["unspecified excluded"],
            ),
            PreparationScoreResult(
                score=45.0,
                excluded=False,
                preference_status="allowed",
                remaining_need=2,
                fairness_quantity=0,
                reasons=["allowed preference"],
            ),
            PreparationScoreResult(
                score=80.0,
                excluded=False,
                preference_status="requested",
                remaining_need=4,
                fairness_quantity=0,
                reasons=["requested preference"],
            ),
        ]

        specs = _build_scope_specs(
            run=self.run,
            need_snapshot=need_snapshot,
            shipper_rule=PreparationShipperRule.objects.get(
                parameter_set=self.parameter_set,
                shipper=self.shipper,
            ),
            asf_shipper=None,
            include_unspecified=False,
            manual_reserve_quantities={self.product.id: 2},
        )

        self.assertEqual([spec["source"] for spec in specs], ["asf_stock", "deposit"])
        self.assertEqual(specs[0]["quantity"], 4)
        self.assertTrue(specs[0]["reserve_quantity"])
        self.assertEqual(specs[1]["product"], alt_product)
        self.assertFalse(specs[1]["reserve_quantity"])

    @patch("wms.preparation.generation.reserve_stock_for_carton_proposal")
    def test_create_shipment_proposal_merges_duplicate_rows_and_reserves_stock_only(
        self,
        mock_reserve_stock,
    ):
        need_snapshot = snapshot_active_recurring_needs(run=self.run)[0]
        deposit_score = PreparationScoreResult(
            score=20.0,
            excluded=False,
            preference_status="allowed",
            remaining_need=2,
            fairness_quantity=0,
            reasons=["allowed preference"],
        )
        stock_score = PreparationScoreResult(
            score=50.0,
            excluded=False,
            preference_status="requested",
            remaining_need=5,
            fairness_quantity=0,
            reasons=["requested preference"],
        )

        proposal = _create_shipment_proposal(
            run=self.run,
            need_snapshot=need_snapshot,
            sequence=1,
            chunk_rows=[
                {
                    "source": "deposit",
                    "quantity": 2,
                    "product": self.product,
                    "score": 20.0,
                    "score_result": deposit_score,
                    "source_carton_id": 11,
                    "source_shipment_id": 21,
                    "reserve_quantity": False,
                },
                {
                    "source": "asf_stock",
                    "quantity": 3,
                    "product": self.product,
                    "score": 50.0,
                    "score_result": stock_score,
                    "source_carton_id": None,
                    "source_shipment_id": None,
                    "reserve_quantity": True,
                },
                {
                    "source": "asf_stock",
                    "quantity": 2,
                    "product": self.product,
                    "score": 40.0,
                    "score_result": stock_score,
                    "source_carton_id": None,
                    "source_shipment_id": None,
                    "reserve_quantity": True,
                },
            ],
            created_by=self.user,
            manual_reserve_quantities={self.product.id: 3},
        )

        carton_rows = list(proposal.carton_proposals.order_by("id"))

        self.assertEqual(_shipment_source([{"source": "deposit"}]), "deposit")
        self.assertEqual(_shipment_source([{"source": "asf_stock"}]), "asf_stock")
        self.assertEqual(proposal.source, "mixed")
        self.assertEqual(proposal.equivalent_units_total, 7)
        self.assertEqual(float(proposal.score), 110.0)
        self.assertEqual(len(carton_rows), 2)
        self.assertEqual([row.quantity for row in carton_rows], [2, 5])
        self.assertEqual(
            proposal.rationale["reasons"],
            ["allowed preference", "requested preference"],
        )
        mock_reserve_stock.assert_called_once()
        self.assertEqual(
            mock_reserve_stock.call_args.kwargs["manual_reserve_quantity"],
            3,
        )
