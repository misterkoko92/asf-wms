from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    PreparationCartonProposal,
    PreparationDecisionAction,
    PreparationDecisionLog,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationReservation,
    PreparationReservationStatus,
    PreparationRun,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    ProductLot,
    ProductLotStatus,
    Shipment,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentStatus,
    Warehouse,
)
from wms.planning.flight_providers import PlanningFlightProviderConfigurationError
from wms.preparation.reservations import reserve_stock_for_carton_proposal


class ScanPreparationViewsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="scan-preparation-staff",
            password="pass1234",  # pragma: allowlist secret
            is_staff=True,
        )
        self.client.force_login(self.staff_user)
        self.parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin UI",
            created_by=self.staff_user,
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
        PreparationShipperRule.objects.create(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
            mode=PreparationShipperMode.ASF_AUTO_ALLOWED,
        )
        self.destination_rule = PreparationDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            max_equivalent_units_per_flight=12,
            max_usable_flights_per_week=2,
            max_equivalent_units_per_week=20,
            max_shipments_per_week=3,
            fairness_weight="1.10",
        )
        self.warehouse = Warehouse.objects.create(name="Main", code="WH-VIEW-PREP")
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
        self.lot = ProductLot.objects.create(
            product=self.product,
            location=self.location,
            quantity_on_hand=20,
            quantity_reserved=0,
            status=ProductLotStatus.AVAILABLE,
        )

    def _create_run_with_proposal(self):
        run = PreparationRun.objects.create(
            parameter_set=self.parameter_set,
            created_by=self.staff_user,
            target_equivalent_units=20,
            target_shipment_count=2,
            target_shipment_size_units=10,
            min_shipment_size_units=5,
            max_shipment_size_units=12,
            flight_window_start=date(2026, 5, 18),
            flight_window_end=date(2026, 5, 24),
        )
        proposal = PreparationShipmentProposal.objects.create(
            run=run,
            shipper=self.shipper,
            recipient_organization=self.recipient,
            destination=self.destination,
            sequence=1,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            equivalent_units_total=10,
            rationale={"reasons": ["requested need covered"]},
        )
        carton_a = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=4,
            equivalent_units_total=4,
            rationale={"score_reasons": ["requested need covered"]},
        )
        carton_b = PreparationCartonProposal.objects.create(
            shipment_proposal=proposal,
            product=self.product,
            source=PreparationProposalSource.ASF_STOCK,
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=6,
            equivalent_units_total=6,
            rationale={"score_reasons": ["requested need covered"]},
        )
        reserve_stock_for_carton_proposal(
            run=run,
            shipment_proposal=proposal,
            carton_proposal=carton_a,
            created_by=self.staff_user,
        )
        reserve_stock_for_carton_proposal(
            run=run,
            shipment_proposal=proposal,
            carton_proposal=carton_b,
            created_by=self.staff_user,
        )
        return run, proposal, carton_a, carton_b

    def test_staff_can_open_preparation_run_list_and_create_page(self):
        list_response = self.client.get(reverse("scan:scan_preparation_run_list"))
        create_response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(list_response, "Runs magasin")
        self.assertContains(create_response, "Nouveau run magasin")

    def test_create_form_exposes_run_inputs(self):
        response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="parameter_set"')
        self.assertContains(response, 'name="shippers"')
        self.assertContains(response, 'name="destinations"')
        self.assertContains(response, 'name="target_equivalent_units"')
        self.assertContains(response, 'name="target_shipment_count"')
        self.assertContains(response, 'name="target_shipment_size_units"')
        self.assertContains(response, 'name="min_shipment_size_units"')
        self.assertContains(response, 'name="max_shipment_size_units"')
        self.assertContains(response, 'name="flight_window_start"')
        self.assertContains(response, 'name="flight_window_end"')

    def test_create_form_uses_verbose_labels_date_inputs_and_select_all_controls(self):
        response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Total colis équivalents cible à préparer sur la période",
        )
        self.assertContains(
            response,
            "Total expéditions cible à proposer sur la période",
        )
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'id="prep-select-all-shippers"')
        self.assertContains(response, 'id="prep-select-all-destinations"')
        self.assertContains(response, "Tout sélectionner")
        self.assertContains(response, "checked")

    def test_create_form_defaults_to_last_used_parameter_set_and_preselects_all_scopes(self):
        previous_parameter_set = PreparationParameterSet.objects.create(
            name="Run magasin précédent",
            created_by=self.staff_user,
            is_current=True,
        )
        PreparationRun.objects.create(
            parameter_set=previous_parameter_set,
            created_by=self.staff_user,
            target_equivalent_units=12,
            target_shipment_count=1,
            target_shipment_size_units=10,
            min_shipment_size_units=1,
            flight_window_start=date(2026, 5, 1),
            flight_window_end=date(2026, 5, 3),
        )

        response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form["parameter_set"].value(), previous_parameter_set.id)
        self.assertEqual(
            sorted(str(value) for value in form["shippers"].value()),
            [str(self.shipper.id)],
        )
        self.assertEqual(
            sorted(str(value) for value in form["destinations"].value()),
            [str(self.destination.id)],
        )

    def test_create_form_defaults_operational_targets_and_s_plus_1_window_from_monday_to_wednesday(
        self,
    ):
        with mock.patch("wms.forms_preparation.timezone.localdate", return_value=date(2026, 4, 8)):
            response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["target_equivalent_units"], 200)
        self.assertEqual(form.initial["target_shipment_count"], 15)
        self.assertEqual(form.initial["target_shipment_size_units"], 10)
        self.assertEqual(form.initial["min_shipment_size_units"], 8)
        self.assertEqual(form.initial["max_shipment_size_units"], 22)
        self.assertEqual(form.initial["flight_window_start"], date(2026, 4, 13))
        self.assertEqual(form.initial["flight_window_end"], date(2026, 4, 19))

    def test_create_form_defaults_flight_window_to_s_plus_2_when_run_launched_from_thursday_to_sunday(
        self,
    ):
        with mock.patch("wms.forms_preparation.timezone.localdate", return_value=date(2026, 4, 9)):
            response = self.client.get(reverse("scan:scan_preparation_run_create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["flight_window_start"], date(2026, 4, 20))
        self.assertEqual(form.initial["flight_window_end"], date(2026, 4, 26))

    def test_staff_can_open_parameter_set_config_page(self):
        response = self.client.get(
            reverse("scan:scan_preparation_parameter_set_config"),
            {"parameter_set": self.parameter_set.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configuration du jeu de paramètres")
        self.assertContains(response, self.parameter_set.name)
        self.assertContains(response, "Capacité max par vol")
        self.assertContains(response, "Coefficient de score")
        self.assertContains(response, 'title="Nombre maximal de colis équivalents')
        self.assertContains(response, 'title="Le poids d&#x27;équité augmente ou réduit')
        self.assertContains(response, 'name="destination_rules-0-allowed_weekdays_selection"')
        self.assertContains(response, 'id="prep-weekday-dropdown-0"')
        self.assertContains(response, 'data-bs-toggle="tooltip"')
        self.assertContains(response, 'onchange="this.form.submit()"')
        self.assertContains(response, "Tous les jours")
        self.assertContains(response, "Jours de vol autorisés")
        self.assertContains(
            response,
            'title="Ne rien sélectionner pour utiliser tous les jours disponibles."',
        )
        self.assertNotContains(
            response, "Ne rien sélectionner pour utiliser tous les jours disponibles.</div>"
        )
        self.assertNotContains(response, ">Ouvrir<")

    def test_parameter_set_config_page_updates_parameter_set_destination_and_shipper_rules(self):
        response = self.client.get(
            reverse("scan:scan_preparation_parameter_set_config"),
            {"parameter_set": self.parameter_set.id},
        )
        self.assertEqual(response.status_code, 200)

        post_data = {
            "parameter_set_id": str(self.parameter_set.id),
            "parameter-name": "Run magasin mis à jour",
            "parameter-notes": "Notes opérateur",
            "parameter-is_current": "on",
            "destination_rules-TOTAL_FORMS": "1",
            "destination_rules-INITIAL_FORMS": "1",
            "destination_rules-MIN_NUM_FORMS": "0",
            "destination_rules-MAX_NUM_FORMS": "1000",
            "destination_rules-0-id": str(self.destination_rule.id),
            "destination_rules-0-max_equivalent_units_per_flight": "14",
            "destination_rules-0-max_usable_flights_per_week": "3",
            "destination_rules-0-max_equivalent_units_per_week": "28",
            "destination_rules-0-max_shipments_per_week": "4",
            "destination_rules-0-fairness_weight": "1.25",
            "destination_rules-0-allowed_weekdays_selection": ["mon", "wed", "fri"],
            "destination_rules-0-is_active": "on",
            "destination_rules-0-notes": "Capacité revue",
            "shipper_rules-TOTAL_FORMS": "1",
            "shipper_rules-INITIAL_FORMS": "1",
            "shipper_rules-MIN_NUM_FORMS": "0",
            "shipper_rules-MAX_NUM_FORMS": "1000",
            "shipper_rules-0-id": str(
                self.parameter_set.shipper_rules.get(shipper=self.shipper).id
            ),
            "shipper_rules-0-mode": PreparationShipperMode.ASF_COMPLEMENT_ALLOWED,
            "shipper_rules-0-score_coefficient": "0.90",
            "shipper_rules-0-is_active": "on",
            "shipper_rules-0-notes": "Priorité terrain",
        }

        post_response = self.client.post(
            reverse("scan:scan_preparation_parameter_set_config"),
            post_data,
            follow=True,
        )

        self.assertEqual(post_response.status_code, 200)
        self.parameter_set.refresh_from_db()
        self.destination_rule.refresh_from_db()
        shipper_rule = PreparationShipperRule.objects.get(
            parameter_set=self.parameter_set,
            shipper=self.shipper,
        )
        self.assertEqual(self.parameter_set.name, "Run magasin mis à jour")
        self.assertEqual(self.parameter_set.notes, "Notes opérateur")
        self.assertTrue(self.parameter_set.is_current)
        self.assertEqual(self.destination_rule.max_equivalent_units_per_flight, 14)
        self.assertEqual(self.destination_rule.max_usable_flights_per_week, 3)
        self.assertEqual(self.destination_rule.allowed_weekdays, ["mon", "wed", "fri"])
        self.assertEqual(str(self.destination_rule.fairness_weight), "1.25")
        self.assertEqual(shipper_rule.mode, PreparationShipperMode.ASF_COMPLEMENT_ALLOWED)
        self.assertEqual(str(shipper_rule.score_coefficient), "0.90")
        self.assertContains(post_response, "Jeu de paramètres enregistré.")

    def test_parameter_set_config_prefills_blank_destination_rule_from_current_planning_rule(self):
        planning_parameter_set = PlanningParameterSet.objects.create(
            name="Planning courant",
            is_current=True,
            created_by=self.staff_user,
        )
        PlanningDestinationRule.objects.create(
            parameter_set=planning_parameter_set,
            destination=self.destination,
            weekly_frequency=3,
            max_cartons_per_flight=7,
            allowed_weekdays=["mon", "wed", "fri"],
            is_active=True,
        )
        self.destination_rule.max_equivalent_units_per_flight = None
        self.destination_rule.max_usable_flights_per_week = None
        self.destination_rule.max_equivalent_units_per_week = None
        self.destination_rule.max_shipments_per_week = None
        self.destination_rule.allowed_weekdays = []
        self.destination_rule.save(
            update_fields=[
                "max_equivalent_units_per_flight",
                "max_usable_flights_per_week",
                "max_equivalent_units_per_week",
                "max_shipments_per_week",
                "allowed_weekdays",
            ]
        )

        response = self.client.get(
            reverse("scan:scan_preparation_parameter_set_config"),
            {"parameter_set": self.parameter_set.id},
        )

        self.assertEqual(response.status_code, 200)
        self.destination_rule.refresh_from_db()
        self.assertEqual(self.destination_rule.max_equivalent_units_per_flight, 7)
        self.assertEqual(self.destination_rule.max_usable_flights_per_week, 3)
        self.assertEqual(self.destination_rule.max_equivalent_units_per_week, 21)
        self.assertEqual(self.destination_rule.max_shipments_per_week, 3)
        self.assertEqual(self.destination_rule.allowed_weekdays, ["mon", "wed", "fri"])

    def test_generation_post_creates_reviewable_run(self):
        with mock.patch("wms.views_scan_preparation.generate_preparation_run") as generate_mock:
            generate_mock.side_effect = lambda **kwargs: kwargs["run"]
            response = self.client.post(
                reverse("scan:scan_preparation_run_create"),
                {
                    "parameter_set": str(self.parameter_set.id),
                    "shippers": [str(self.shipper.id)],
                    "destinations": [str(self.destination.id)],
                    "target_equivalent_units": "20",
                    "target_shipment_count": "2",
                    "target_shipment_size_units": "10",
                    "min_shipment_size_units": "5",
                    "max_shipment_size_units": "12",
                    "flight_window_start": "2026-05-18",
                    "flight_window_end": "2026-05-24",
                },
            )

        created_run = PreparationRun.objects.get(parameter_set=self.parameter_set)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("scan:scan_preparation_run_detail", args=[created_run.id]),
        )
        generate_mock.assert_called_once()

    def test_generation_post_surfaces_flight_import_errors_without_leaving_orphan_run(self):
        with mock.patch("wms.views_scan_preparation.generate_preparation_run") as generate_mock:
            generate_mock.side_effect = PlanningFlightProviderConfigurationError(
                "PLANNING_FLIGHT_API_KEY is required for planning API imports."
            )
            response = self.client.post(
                reverse("scan:scan_preparation_run_create"),
                {
                    "parameter_set": str(self.parameter_set.id),
                    "shippers": [str(self.shipper.id)],
                    "destinations": [str(self.destination.id)],
                    "target_equivalent_units": "20",
                    "target_shipment_count": "2",
                    "target_shipment_size_units": "10",
                    "min_shipment_size_units": "5",
                    "max_shipment_size_units": "12",
                    "flight_window_start": "2026-05-18",
                    "flight_window_end": "2026-05-24",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Impossible de charger les vols pour ce run magasin",
        )
        self.assertEqual(PreparationRun.objects.count(), 0)

    def test_review_page_shows_proposal_rows_score_reasons_fallback_warning_and_stale_markers(self):
        run, proposal, carton_a, carton_b = self._create_run_with_proposal()
        run.parameter_snapshot = {
            "flight_source": {
                "used_fallback": True,
                "fallback_reason": "upstream unavailable",
                "freshness_days": 4,
            }
        }
        run.save(update_fields=["parameter_snapshot"])
        proposal.status = PreparationShipmentProposalStatus.NEEDS_RECALC
        proposal.rationale = {"reasons": ["requested need covered", "fallback flight batch"]}
        proposal.save(update_fields=["status", "rationale", "updated_at"])

        response = self.client.get(reverse("scan:scan_preparation_run_detail", args=[run.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.shipper_contact.name)
        self.assertContains(response, self.recipient_contact.name)
        self.assertContains(response, "requested need covered")
        self.assertContains(response, "upstream unavailable")
        self.assertContains(response, "needs-recalc")
        self.assertContains(response, f'value="{proposal.id}"')
        self.assertContains(response, f'value="{carton_a.id}"')
        self.assertContains(response, f'value="{carton_b.id}"')

    def test_review_page_exposes_shipment_and_carton_checkboxes_and_actions(self):
        run, proposal, carton_a, carton_b = self._create_run_with_proposal()

        response = self.client.get(reverse("scan:scan_preparation_run_detail", args=[run.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="selected_shipment_ids"')
        self.assertContains(response, 'name="selected_carton_ids"')
        self.assertContains(response, 'value="accept_all"')
        self.assertContains(response, 'value="accept_selected"')
        self.assertContains(response, 'value="reject_keep_draft"')
        self.assertContains(response, 'value="reject_delete"')
        self.assertContains(response, 'value="convert_accepted"')

    def test_operator_can_accept_all_and_accept_partial(self):
        run, proposal, carton_a, carton_b = self._create_run_with_proposal()

        response = self.client.post(
            reverse("scan:scan_preparation_run_detail", args=[run.id]),
            {"action": "accept_all"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        carton_a.refresh_from_db()
        carton_b.refresh_from_db()
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.ACCEPTED)
        self.assertEqual(carton_a.status, PreparationShipmentProposalStatus.ACCEPTED)
        self.assertEqual(carton_b.status, PreparationShipmentProposalStatus.ACCEPTED)

        partial_run, partial_proposal, partial_carton_a, partial_carton_b = (
            self._create_run_with_proposal()
        )
        partial_response = self.client.post(
            reverse("scan:scan_preparation_run_detail", args=[partial_run.id]),
            {
                "action": "accept_selected",
                "selected_carton_ids": [str(partial_carton_a.id)],
            },
            follow=True,
        )

        self.assertEqual(partial_response.status_code, 200)
        partial_proposal.refresh_from_db()
        partial_carton_a.refresh_from_db()
        partial_carton_b.refresh_from_db()
        self.assertEqual(partial_proposal.status, PreparationShipmentProposalStatus.PARTIAL)
        self.assertEqual(partial_carton_a.status, PreparationShipmentProposalStatus.ACCEPTED)
        self.assertEqual(partial_carton_b.status, PreparationShipmentProposalStatus.PROPOSED)

    def test_operator_can_refuse_keep_draft_and_refuse_delete(self):
        run, proposal, carton_a, carton_b = self._create_run_with_proposal()

        response = self.client.post(
            reverse("scan:scan_preparation_run_detail", args=[run.id]),
            {
                "action": "reject_keep_draft",
                "selected_carton_ids": [str(carton_a.id)],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        carton_a.refresh_from_db()
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.PARTIAL)
        self.assertEqual(carton_a.status, PreparationShipmentProposalStatus.REJECTED)
        self.assertEqual(
            PreparationReservation.objects.filter(
                carton_proposal=carton_a,
                status=PreparationReservationStatus.ACTIVE,
            ).count(),
            0,
        )
        self.assertTrue(
            PreparationDecisionLog.objects.filter(
                carton_proposal=carton_a,
                action=PreparationDecisionAction.REJECT_KEEP_DRAFT,
            ).exists()
        )

        delete_run, delete_proposal, delete_carton_a, delete_carton_b = (
            self._create_run_with_proposal()
        )
        delete_response = self.client.post(
            reverse("scan:scan_preparation_run_detail", args=[delete_run.id]),
            {
                "action": "reject_delete",
                "selected_shipment_ids": [str(delete_proposal.id)],
            },
            follow=True,
        )

        self.assertEqual(delete_response.status_code, 200)
        delete_proposal.refresh_from_db()
        delete_carton_a.refresh_from_db()
        delete_carton_b.refresh_from_db()
        self.assertEqual(delete_proposal.status, PreparationShipmentProposalStatus.REJECTED)
        self.assertEqual(delete_carton_a.status, PreparationShipmentProposalStatus.REJECTED)
        self.assertEqual(delete_carton_b.status, PreparationShipmentProposalStatus.REJECTED)
        self.assertContains(delete_response, "Aucune proposition.")

    def test_operator_can_convert_accepted_proposals_from_review_page(self):
        run, proposal, carton_a, carton_b = self._create_run_with_proposal()
        proposal.status = PreparationShipmentProposalStatus.ACCEPTED
        proposal.save(update_fields=["status", "updated_at"])
        carton_a.status = PreparationShipmentProposalStatus.ACCEPTED
        carton_a.save(update_fields=["status", "updated_at"])
        carton_b.status = PreparationShipmentProposalStatus.ACCEPTED
        carton_b.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("scan:scan_preparation_run_detail", args=[run.id]),
            {"action": "convert_accepted"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        carton_a.refresh_from_db()
        carton_b.refresh_from_db()
        shipment = proposal.converted_shipment

        self.assertIsNotNone(shipment)
        self.assertEqual(shipment.status, ShipmentStatus.PICKING)
        self.assertEqual(proposal.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(carton_a.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(carton_b.status, PreparationShipmentProposalStatus.CONVERTED)
        self.assertEqual(Shipment.objects.filter(id=shipment.id).count(), 1)
