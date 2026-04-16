from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from wms.models import (
    AccountDocument,
    AssociationBillingChangeRequest,
    AssociationBillingProfile,
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    BillingAssociationPriceOverride,
    BillingDocument,
    BillingDocumentCorrectionState,
    BillingDocumentKind,
    BillingDocumentLine,
    BillingDocumentReceipt,
    BillingDocumentShipment,
    BillingDocumentStatus,
    BillingIssue,
    BillingPayment,
    Carton,
    CartonStatus,
    CommunicationChannel,
    CommunicationTemplate,
    DocumentReviewStatus,
    IntegrationEvent,
    Order,
    OrderDocument,
    OrderLine,
    PlanningRun,
    PlanningRunStatus,
    PortalAccessGrant,
    PortalAccessRole,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationRun,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    PreparationShipperRule,
    Product,
    ProductLot,
    ProductLotStatus,
    PublicAccountRequest,
    Receipt,
    ReceiptShipmentAllocation,
    RecipientProductPreference,
    RecurringPreparationNeed,
    Shipment,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    ShipmentValidationStatus,
    VolunteerAvailability,
    VolunteerConstraint,
    VolunteerProfile,
)


class SeedLocalExhaustiveDataCommandTests(TestCase):
    def test_command_creates_named_local_dataset_summary(self):
        output = StringIO()

        call_command(
            "seed_local_exhaustive_data",
            "--scenario=local-exhaustive",
            stdout=output,
        )

        rendered = output.getvalue()
        self.assertIn("Scenario local-exhaustive ready", rendered)
        self.assertIn("Users:", rendered)
        self.assertIn("URLs:", rendered)
        self.assertIn("users=", rendered)
        self.assertIn("shipments=", rendered)
        self.assertIn("planning_runs=", rendered)
        self.assertIn("- portal recipient:", rendered)
        self.assertIn("- portal multi:", rendered)
        self.assertIn("- planning runs:", rendered)

    def test_command_creates_local_users_profiles_and_contact_roles(self):
        call_command("seed_local_exhaustive_data", "--scenario=users")

        self.assertGreaterEqual(
            AssociationProfile.objects.filter(user__username__contains="users").count(),
            2,
        )
        self.assertGreaterEqual(
            AssociationPortalContact.objects.filter(email__contains="users").count(),
            4,
        )
        self.assertGreaterEqual(ShipmentShipper.objects.count(), 2)
        self.assertGreaterEqual(ShipmentRecipientOrganization.objects.count(), 2)
        self.assertGreaterEqual(ShipmentAuthorizedRecipientContact.objects.count(), 2)
        self.assertGreaterEqual(Product.objects.filter(name__contains="[LOCAL users]").count(), 3)
        self.assertTrue(
            CommunicationTemplate.objects.filter(
                label__icontains="users",
                channel=CommunicationChannel.EMAIL,
            ).exists()
        )
        self.assertTrue(
            CommunicationTemplate.objects.filter(
                label__icontains="users",
                channel=CommunicationChannel.WHATSAPP,
            ).exists()
        )

    def test_command_marks_seeded_local_shippers_and_recipients_as_validated(self):
        call_command("seed_local_exhaustive_data", "--scenario=users")

        self.assertGreaterEqual(
            ShipmentShipper.objects.filter(
                organization__name__contains="[LOCAL users] Association",
                validation_status=ShipmentValidationStatus.VALIDATED,
                is_active=True,
            ).count(),
            2,
        )
        self.assertEqual(
            ShipmentRecipientOrganization.objects.filter(
                organization__name__contains="[LOCAL users] Structure",
                validation_status=ShipmentValidationStatus.PENDING,
            ).count(),
            0,
        )
        self.assertGreaterEqual(
            ShipmentRecipientOrganization.objects.filter(
                organization__name__contains="[LOCAL users] Structure",
                validation_status=ShipmentValidationStatus.VALIDATED,
                is_active=True,
            ).count(),
            3,
        )

    def test_command_seeds_pending_recipient_validation_duplicate_cases(self):
        call_command("seed_local_exhaustive_data", "--scenario=validations")

        pending_runtimes = ShipmentRecipientOrganization.objects.filter(
            validation_status=ShipmentValidationStatus.PENDING,
            is_active=True,
            organization__name__in=[
                "[LOCAL validations] Validation Merge",
                "[LOCAL validations] Validation Duplicate",
            ],
        ).select_related("organization", "destination")

        self.assertEqual(pending_runtimes.count(), 2)
        self.assertEqual(
            ShipmentRecipientOrganization.objects.filter(
                validation_status=ShipmentValidationStatus.VALIDATED,
                is_active=True,
                organization__name__in=[
                    "[LOCAL validations] Validation Merge",
                    "[LOCAL validations] Validation Duplicate",
                ],
            ).count(),
            2,
        )
        self.assertEqual(
            ShipmentRecipientContact.objects.filter(
                recipient_organization__in=pending_runtimes,
                is_active=True,
            ).count(),
            2,
        )
        self.assertEqual(
            ShipmentShipperRecipientLink.objects.filter(
                recipient_organization__in=pending_runtimes,
                is_active=True,
            ).count(),
            2,
        )
        self.assertEqual(
            ShipmentAuthorizedRecipientContact.objects.filter(
                link__recipient_organization__in=pending_runtimes,
                is_active=True,
                is_default=True,
            ).count(),
            2,
        )

    def test_command_creates_actionable_shipments_cartons_and_alert_rows(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=ops",
            "--with-queue-backlog",
        )

        self.assertTrue(
            Shipment.objects.filter(
                shipper_name__contains="[LOCAL ops]",
                reference__startswith="EXP-TEMP-",
            ).exists()
        )
        self.assertGreaterEqual(Carton.objects.filter(status=CartonStatus.PACKED).count(), 1)
        self.assertGreaterEqual(Carton.objects.filter(status=CartonStatus.LABELED).count(), 1)
        self.assertGreaterEqual(Carton.objects.filter(status=CartonStatus.SHIPPED).count(), 1)
        self.assertGreaterEqual(
            Shipment.objects.filter(
                shipper_name__contains="[LOCAL ops]",
                is_disputed=True,
            ).count(),
            1,
        )
        self.assertTrue(
            Shipment.objects.filter(
                shipper_name__contains="[LOCAL ops]",
                status=ShipmentStatus.DELIVERED,
                closed_at__isnull=True,
            ).exists()
        )
        self.assertTrue(
            ShipmentTrackingEvent.objects.filter(status=ShipmentTrackingStatus.PLANNED).exists()
        )
        self.assertTrue(
            ShipmentTrackingEvent.objects.filter(
                status=ShipmentTrackingStatus.RECEIVED_RECIPIENT
            ).exists()
        )
        self.assertGreaterEqual(IntegrationEvent.objects.filter(source="wms.email").count(), 1)
        self.assertGreaterEqual(
            IntegrationEvent.objects.filter(source="wms.document_scan").count(),
            1,
        )

    def test_command_creates_portal_orders_documents_and_billing_requests(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=portal",
            "--with-demo-documents",
        )

        self.assertGreaterEqual(Order.objects.count(), 2)
        self.assertGreaterEqual(AccountDocument.objects.count(), 1)
        self.assertGreaterEqual(OrderDocument.objects.count(), 1)
        self.assertGreaterEqual(AssociationBillingChangeRequest.objects.count(), 1)
        self.assertGreaterEqual(AssociationRecipient.objects.count(), 2)
        self.assertGreaterEqual(PublicAccountRequest.objects.count(), 1)
        self.assertTrue(
            AccountDocument.objects.filter(status=DocumentReviewStatus.PENDING).exists()
        )
        self.assertTrue(OrderDocument.objects.filter(status=DocumentReviewStatus.APPROVED).exists())

    def test_command_can_seed_solved_planning_and_volunteer_profiles(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=planning",
            "--with-planning-solve",
        )

        self.assertGreaterEqual(
            VolunteerProfile.objects.filter(user__username__contains="planning").count(),
            3,
        )
        self.assertTrue(
            VolunteerProfile.objects.filter(
                user__username__contains="planning",
                must_change_password=True,
            ).exists()
        )
        self.assertGreaterEqual(
            VolunteerAvailability.objects.filter(
                volunteer__user__username__contains="planning"
            ).count(),
            3,
        )
        self.assertGreaterEqual(
            VolunteerConstraint.objects.filter(
                volunteer__user__username__contains="planning"
            ).count(),
            2,
        )
        self.assertTrue(PlanningRun.objects.filter(status=PlanningRunStatus.SOLVED).exists())

    def test_command_creates_preparation_run_seed_configuration(self):
        call_command("seed_local_exhaustive_data", "--scenario=preparation")

        parameter_set = PreparationParameterSet.objects.get(name__icontains="[LOCAL preparation]")
        self.assertTrue(parameter_set.is_current)
        self.assertGreaterEqual(
            PreparationDestinationRule.objects.filter(
                parameter_set=parameter_set, is_active=True
            ).count(),
            2,
        )
        self.assertGreaterEqual(
            PreparationShipperRule.objects.filter(
                parameter_set=parameter_set, is_active=True
            ).count(),
            2,
        )
        self.assertGreaterEqual(RecurringPreparationNeed.objects.count(), 2)
        self.assertGreaterEqual(RecipientProductPreference.objects.count(), 4)
        self.assertFalse(
            ShipmentRecipientOrganization.objects.filter(
                organization__name__contains="[LOCAL preparation]",
                validation_status="pending",
            ).exists()
        )

    def test_command_creates_explicit_portal_access_grants_and_multi_scope_user(self):
        call_command("seed_local_exhaustive_data", "--scenario=portal-grants")

        shipper_user = get_user_model().objects.get(username="portal-portal-grants-a")
        recipient_user = get_user_model().objects.get(username="portal-portal-grants-recipient")
        multi_user = get_user_model().objects.get(username="portal-portal-grants-multi")

        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=shipper_user,
                role=PortalAccessRole.SHIPPER_ADMIN,
                shipper__organization__name__contains="[LOCAL portal-grants] Association A",
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            PortalAccessGrant.objects.filter(
                user=recipient_user,
                role=PortalAccessRole.RECIPIENT_ADMIN,
                recipient_organization__organization__name__contains="[LOCAL portal-grants] Structure ALPHA",
                is_active=True,
            ).exists()
        )
        self.assertEqual(
            PortalAccessGrant.objects.filter(user=multi_user, is_active=True).count(),
            2,
        )
        self.assertEqual(
            set(
                PortalAccessGrant.objects.filter(user=multi_user, is_active=True).values_list(
                    "role", flat=True
                )
            ),
            {PortalAccessRole.SHIPPER_ADMIN, PortalAccessRole.RECIPIENT_ADMIN},
        )

    def test_command_creates_preparation_runs_in_multiple_review_states(self):
        call_command("seed_local_exhaustive_data", "--scenario=prep-runs")

        runs = PreparationRun.objects.filter(parameter_set__name__icontains="[LOCAL prep-runs]")
        self.assertTrue(runs.filter(status=PreparationRunStatus.GENERATED).exists())
        self.assertTrue(runs.filter(status=PreparationRunStatus.FROZEN).exists())
        self.assertTrue(runs.filter(status=PreparationRunStatus.CONVERTED).exists())
        self.assertTrue(
            PreparationShipmentProposal.objects.filter(
                run__in=runs,
                status=PreparationShipmentProposalStatus.ACCEPTED,
            ).exists()
        )
        self.assertTrue(
            PreparationShipmentProposal.objects.filter(
                run__in=runs,
                status__in=[
                    PreparationShipmentProposalStatus.REJECTED,
                    PreparationShipmentProposalStatus.PARTIAL,
                ],
            ).exists()
        )
        self.assertTrue(
            Shipment.objects.filter(
                preparation_proposals__run__in=runs,
                status=ShipmentStatus.PICKING,
            ).exists()
        )

    def test_command_creates_ready_and_solved_planning_runs_for_local_launch(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=planning-launch",
            "--with-planning-solve",
        )

        planning_runs = PlanningRun.objects.filter(
            parameter_set__name__icontains="[LOCAL planning-launch] Planning",
        )
        ready_run = planning_runs.filter(status=PlanningRunStatus.READY).first()
        solved_run = planning_runs.filter(status=PlanningRunStatus.SOLVED).first()

        self.assertIsNotNone(ready_run)
        self.assertIsNotNone(solved_run)
        self.assertIsNotNone(ready_run.flight_batch_id)
        self.assertTrue(ready_run.shipment_snapshots.exists())
        self.assertTrue(ready_run.volunteer_snapshots.exists())
        self.assertTrue(ready_run.flight_snapshots.exists())
        self.assertTrue(solved_run.versions.exists())

    def test_command_is_idempotent_and_fresh_can_reset_previous_runtime_rows(self):
        Shipment.objects.create(
            reference="OUTSIDER-001",
            status=ShipmentStatus.DRAFT,
            shipper_name="Outsider shipper",
            recipient_name="Outsider recipient",
            destination_address="Rue externe",
            destination_country="France",
        )

        call_command(
            "seed_local_exhaustive_data",
            "--scenario=repeatable",
            "--with-demo-documents",
            "--with-queue-backlog",
        )
        first_counts = {
            "shipments": Shipment.objects.filter(reference__contains="REPEATABLE").count(),
            "profiles": AssociationProfile.objects.filter(
                user__username__contains="repeatable"
            ).count(),
            "documents": BillingDocument.objects.filter(
                association_profile__user__username__contains="repeatable"
            ).count(),
            "events": IntegrationEvent.objects.filter(external_id__contains="repeatable").count(),
        }

        call_command(
            "seed_local_exhaustive_data",
            "--scenario=repeatable",
            "--with-demo-documents",
            "--with-queue-backlog",
        )

        self.assertEqual(
            Shipment.objects.filter(reference__contains="REPEATABLE").count(),
            first_counts["shipments"],
        )
        self.assertEqual(
            AssociationProfile.objects.filter(user__username__contains="repeatable").count(),
            first_counts["profiles"],
        )
        self.assertEqual(
            BillingDocument.objects.filter(
                association_profile__user__username__contains="repeatable"
            ).count(),
            first_counts["documents"],
        )
        self.assertEqual(
            IntegrationEvent.objects.filter(external_id__contains="repeatable").count(),
            first_counts["events"],
        )

        call_command(
            "seed_local_exhaustive_data",
            "--scenario=after-reset",
            "--fresh",
        )

        self.assertFalse(Shipment.objects.filter(reference="OUTSIDER-001").exists())
        self.assertTrue(Shipment.objects.filter(reference__startswith="LOCAL-AFTER-RESET").exists())

    def test_command_creates_billing_documents_receipts_and_price_overrides(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=billing",
            "--with-demo-documents",
        )

        self.assertGreaterEqual(
            AssociationBillingProfile.objects.filter(
                association_profile__user__username__contains="billing"
            ).count(),
            2,
        )
        self.assertGreaterEqual(
            BillingAssociationPriceOverride.objects.filter(
                association_billing_profile__association_profile__user__username__contains="billing"
            ).count(),
            2,
        )
        self.assertTrue(
            BillingDocument.objects.filter(
                association_profile__user__username__contains="billing",
                kind=BillingDocumentKind.QUOTE,
                status=BillingDocumentStatus.ISSUED,
            ).exists()
        )
        self.assertTrue(
            BillingDocument.objects.filter(
                association_profile__user__username__contains="billing",
                kind=BillingDocumentKind.INVOICE,
                status=BillingDocumentStatus.PARTIALLY_PAID,
            ).exists()
        )
        self.assertTrue(
            BillingDocument.objects.filter(
                association_profile__user__username__contains="billing",
                kind=BillingDocumentKind.CREDIT_NOTE,
                status=BillingDocumentStatus.ISSUED,
            ).exists()
        )
        self.assertTrue(
            BillingDocument.objects.filter(
                association_profile__user__username__contains="billing",
                correction_state=BillingDocumentCorrectionState.IN_REVIEW,
            ).exists()
        )
        self.assertGreaterEqual(
            BillingDocumentShipment.objects.filter(
                document__association_profile__user__username__contains="billing"
            ).count(),
            2,
        )
        self.assertGreaterEqual(
            BillingDocumentReceipt.objects.filter(
                document__association_profile__user__username__contains="billing"
            ).count(),
            1,
        )
        self.assertGreaterEqual(
            BillingDocumentLine.objects.filter(
                document__association_profile__user__username__contains="billing"
            ).count(),
            4,
        )
        self.assertGreaterEqual(
            BillingPayment.objects.filter(
                document__association_profile__user__username__contains="billing"
            ).count(),
            1,
        )
        self.assertGreaterEqual(
            BillingIssue.objects.filter(
                document__association_profile__user__username__contains="billing"
            ).count(),
            1,
        )
        self.assertGreaterEqual(Receipt.objects.count(), 2)
        self.assertGreaterEqual(ReceiptShipmentAllocation.objects.count(), 1)

    def test_command_lights_up_dashboard_cards_and_extended_states(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=dashboard",
            "--with-demo-documents",
            "--with-queue-backlog",
            "--with-e2e-baseline",
        )
        staff_user = get_user_model().objects.get(username="scan-dashboard-admin")
        self.client.force_login(staff_user)

        response = self.client.get(reverse("scan:scan_dashboard"))
        self.assertEqual(response.status_code, 200)

        shipment_cards = {
            card["label"]: card["value"] for card in response.context["shipment_cards"]
        }
        self.assertGreaterEqual(shipment_cards["Brouillons"], 1)
        self.assertGreaterEqual(shipment_cards["En cours"], 1)
        self.assertGreaterEqual(shipment_cards["Prêtes"], 1)
        self.assertGreaterEqual(shipment_cards["Litiges ouverts"], 1)

        carton_cards = {card["label"]: card["value"] for card in response.context["carton_cards"]}
        self.assertGreaterEqual(carton_cards["En préparation"], 1)
        self.assertGreaterEqual(carton_cards["Prêts non affectés"], 1)
        self.assertGreaterEqual(carton_cards["Affectés non étiquetés"], 1)
        self.assertGreaterEqual(carton_cards["Étiquetés"], 1)
        self.assertGreaterEqual(carton_cards["Colis expédiés"], 1)

        stock_cards = {card["label"]: card["value"] for card in response.context["stock_cards"]}
        self.assertGreaterEqual(stock_cards["Produits actifs"], 1)
        self.assertGreaterEqual(stock_cards["Lots disponibles"], 1)
        self.assertGreaterEqual(stock_cards["Quantité disponible"], 1)
        self.assertGreaterEqual(stock_cards["Stock bas (< 20)"], 1)

        flow_cards = {card["label"]: card["value"] for card in response.context["flow_cards"]}
        self.assertGreaterEqual(flow_cards["Réceptions en attente"], 1)
        self.assertGreaterEqual(flow_cards["Cmd en attente de validation"], 1)
        self.assertGreaterEqual(flow_cards["Cmd à modifier"], 1)
        self.assertGreaterEqual(flow_cards["Cmd validées sans expédition"], 1)

        tracking_cards = {
            card["label"]: card["value"] for card in response.context["tracking_cards"]
        }
        self.assertGreaterEqual(tracking_cards["Planifiées sans mise à bord >72h"], 1)
        self.assertGreaterEqual(tracking_cards["Expédiées sans reçu escale >72h"], 1)
        self.assertGreaterEqual(tracking_cards["Reçu escale sans livraison >72h"], 1)
        self.assertGreaterEqual(tracking_cards["Dossiers clôturables"], 1)

        technical_cards = {
            card["label"]: card["value"] for card in response.context["technical_cards"]
        }
        self.assertGreaterEqual(technical_cards["Queue email en attente"], 1)
        self.assertGreaterEqual(technical_cards["Queue email en traitement"], 1)
        self.assertGreaterEqual(technical_cards["Queue email en échec"], 1)
        self.assertGreaterEqual(technical_cards["Queue email bloquée (timeout)"], 1)

        document_scan_cards = {
            card["label"]: card["value"] for card in response.context["document_scan_cards"]
        }
        self.assertGreaterEqual(document_scan_cards["Queue scan doc en attente"], 1)
        self.assertGreaterEqual(document_scan_cards["Queue scan doc en traitement"], 1)
        self.assertGreaterEqual(document_scan_cards["Queue scan doc en échec"], 1)
        self.assertGreaterEqual(document_scan_cards["Queue scan doc bloquée (timeout)"], 1)

        workflow_cards = {
            card["label"]: card["value"] for card in response.context["workflow_blockage_cards"]
        }
        self.assertGreaterEqual(workflow_cards["Expéditions Création/En cours >72h"], 1)
        self.assertGreaterEqual(workflow_cards["Cmd validées sans expédition >72h"], 1)
        self.assertGreaterEqual(workflow_cards["Dossiers livrés non clos"], 1)
        self.assertGreaterEqual(workflow_cards["Dossiers en litige ouverts"], 1)

        self.assertTrue(response.context["low_stock_rows"])
        self.assertTrue(response.context["action_queue_rows"])

        portal_user = get_user_model().objects.get(username="portal-dashboard-a")
        self.client.force_login(portal_user)
        portal_response = self.client.get(reverse("portal:portal_dashboard"))
        self.assertEqual(portal_response.status_code, 200)
        self.assertIn("dashboard_kpis", portal_response.context)
        self.assertContains(portal_response, "Étape suivante")
        self.assertTrue(list(portal_response.context["orders"]))

    def test_command_creates_status_change_ready_orders_and_documents(self):
        call_command(
            "seed_local_exhaustive_data",
            "--scenario=notifications",
            "--with-demo-documents",
        )

        self.assertGreaterEqual(
            Order.objects.filter(
                association_contact__name__contains="[LOCAL notifications]"
            ).count(),
            4,
        )
        self.assertGreaterEqual(
            OrderLine.objects.filter(
                order__association_contact__name__contains="[LOCAL notifications]"
            ).count(),
            4,
        )
        self.assertTrue(
            ProductLot.objects.filter(
                product__name__contains="[LOCAL notifications]",
                status=ProductLotStatus.QUARANTINED,
            ).exists()
        )
        self.assertTrue(
            ProductLot.objects.filter(
                product__name__contains="[LOCAL notifications]",
                status=ProductLotStatus.EXPIRED,
            ).exists()
        )
