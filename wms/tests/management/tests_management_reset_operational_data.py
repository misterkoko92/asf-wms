from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    AssociationPortalContact,
    AssociationProfile,
    AssociationRecipient,
    CartonSequence,
    Destination,
    Location,
    PlanningDestinationRule,
    PlanningParameterSet,
    PublicAccountRequest,
    ReceiptDonorSequence,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    Warehouse,
    WmsRuntimeSettings,
)
from wms.reset_operational_data import (
    ResetOperationalDataSummary,
    _existing_table_labels,
    _validate_configuration,
    render_reset_summary,
    reset_operational_data,
)


class ResetOperationalDataCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="association-test",
            email="association@example.com",
        )
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")
        self.location = Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="1",
            shelf="1",
        )
        self.runtime_settings, _ = WmsRuntimeSettings.objects.get_or_create(pk=1)
        self.correspondent = Contact.objects.create(
            name="Correspondent A",
            contact_type=ContactType.ORGANIZATION,
        )
        self.association = Contact.objects.create(
            name="Association A",
            contact_type=ContactType.ORGANIZATION,
            email="association@example.com",
        )
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="CDG",
            country="France",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.recipient = Contact.objects.create(
            name="Recipient A",
            contact_type=ContactType.ORGANIZATION,
            email="recipient@example.com",
        )
        self.donor = Contact.objects.create(
            name="Donor A",
            contact_type=ContactType.ORGANIZATION,
        )
        self.receipt_donor_sequence = ReceiptDonorSequence.objects.create(
            year=2026,
            donor=self.donor,
            last_number=3,
        )
        self.carton_sequence = CartonSequence.objects.create(
            family="MM",
            last_number=7,
        )
        self.parameter_set = PlanningParameterSet.objects.create(name="Main Planning Set")
        self.destination_rule = PlanningDestinationRule.objects.create(
            parameter_set=self.parameter_set,
            destination=self.destination,
            label="CDG Rule",
            is_active=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.association,
        )
        self.portal_contact = AssociationPortalContact.objects.create(
            profile=self.profile,
            first_name="Alice",
            last_name="Admin",
            email="alice@example.com",
            is_administrative=True,
        )
        self.association_recipient = AssociationRecipient.objects.create(
            association_contact=self.association,
            destination=self.destination,
            name="Association Recipient",
            address_line1="1 rue de Paris",
            city="Paris",
            country="France",
        )
        self.public_account_request = PublicAccountRequest.objects.create(
            contact=self.association,
            association_name="Association A",
            email="association@example.com",
            address_line1="1 rue de Paris",
            city="Paris",
            country="France",
        )
        self.shipper_referent = Contact.objects.create(
            name="Alice Shipper",
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Shipper",
            organization=self.association,
            email="alice.shipper@example.com",
            is_active=True,
        )
        self.recipient_referent = Contact.objects.create(
            name="Bob Recipient",
            contact_type=ContactType.PERSON,
            first_name="Bob",
            last_name="Recipient",
            organization=self.recipient,
            email="bob.recipient@example.com",
            is_active=True,
        )
        self.shipment_shipper = ShipmentShipper.objects.create(
            organization=self.association,
            default_contact=self.shipper_referent,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.shipment_recipient_organization = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient,
            destination=self.destination,
            validation_status=ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.shipment_recipient_contact = ShipmentRecipientContact.objects.create(
            recipient_organization=self.shipment_recipient_organization,
            contact=self.recipient_referent,
            is_active=True,
        )
        self.shipment_link = ShipmentShipperRecipientLink.objects.create(
            shipper=self.shipment_shipper,
            recipient_organization=self.shipment_recipient_organization,
            is_active=True,
        )
        self.shipment_authorized_contact = ShipmentAuthorizedRecipientContact.objects.create(
            link=self.shipment_link,
            recipient_contact=self.shipment_recipient_contact,
            is_default=True,
            is_active=True,
        )

    def test_dry_run_reports_deleted_and_preserved_models_without_writing(self):
        stdout = StringIO()

        call_command("reset_operational_data", "--dry-run", stdout=stdout)

        self.assertIn("DRY RUN", stdout.getvalue())
        self.assertTrue(Contact.objects.filter(pk=self.correspondent.pk).exists())
        self.assertTrue(Destination.objects.filter(pk=self.destination.pk).exists())
        self.assertTrue(AssociationProfile.objects.filter(pk=self.profile.pk).exists())
        self.assertTrue(AssociationPortalContact.objects.filter(pk=self.portal_contact.pk).exists())
        self.assertTrue(
            AssociationRecipient.objects.filter(pk=self.association_recipient.pk).exists()
        )
        self.assertTrue(
            PublicAccountRequest.objects.filter(pk=self.public_account_request.pk).exists()
        )
        self.assertTrue(ShipmentShipper.objects.filter(pk=self.shipment_shipper.pk).exists())
        self.assertTrue(
            ShipmentRecipientOrganization.objects.filter(
                pk=self.shipment_recipient_organization.pk
            ).exists()
        )
        self.assertTrue(
            ShipmentRecipientContact.objects.filter(pk=self.shipment_recipient_contact.pk).exists()
        )
        self.assertTrue(
            ShipmentShipperRecipientLink.objects.filter(pk=self.shipment_link.pk).exists()
        )
        self.assertTrue(
            ShipmentAuthorizedRecipientContact.objects.filter(
                pk=self.shipment_authorized_contact.pk
            ).exists()
        )
        self.assertTrue(
            PlanningDestinationRule.objects.filter(pk=self.destination_rule.pk).exists()
        )
        self.assertTrue(
            ReceiptDonorSequence.objects.filter(pk=self.receipt_donor_sequence.pk).exists()
        )
        self.assertTrue(CartonSequence.objects.filter(pk=self.carton_sequence.pk).exists())
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertTrue(WmsRuntimeSettings.objects.filter(pk=self.runtime_settings.pk).exists())
        self.assertTrue(PlanningParameterSet.objects.filter(pk=self.parameter_set.pk).exists())

    def test_apply_deletes_operational_models_and_preserves_reference_models(self):
        stdout = StringIO()

        call_command("reset_operational_data", "--apply", stdout=stdout)

        self.assertIn("APPLY", stdout.getvalue())
        self.assertFalse(Contact.objects.exists())
        self.assertFalse(Destination.objects.exists())
        self.assertFalse(AssociationProfile.objects.exists())
        self.assertFalse(AssociationPortalContact.objects.exists())
        self.assertFalse(AssociationRecipient.objects.exists())
        self.assertFalse(PublicAccountRequest.objects.exists())
        self.assertFalse(ShipmentShipper.objects.exists())
        self.assertFalse(ShipmentRecipientOrganization.objects.exists())
        self.assertFalse(ShipmentRecipientContact.objects.exists())
        self.assertFalse(ShipmentShipperRecipientLink.objects.exists())
        self.assertFalse(ShipmentAuthorizedRecipientContact.objects.exists())
        self.assertFalse(PlanningDestinationRule.objects.exists())
        self.assertFalse(ReceiptDonorSequence.objects.exists())
        self.assertFalse(CartonSequence.objects.exists())
        self.assertTrue(Warehouse.objects.filter(pk=self.warehouse.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertTrue(WmsRuntimeSettings.objects.filter(pk=self.runtime_settings.pk).exists())
        self.assertTrue(PlanningParameterSet.objects.filter(pk=self.parameter_set.pk).exists())

    def test_render_reset_summary_lists_missing_tables(self):
        summary = ResetOperationalDataSummary(
            mode="DRY RUN",
            delete_counts_before={"wms.Order": 1},
            delete_counts_after={"wms.Order": 1},
            keep_counts_before={"wms.Warehouse": 1},
            keep_counts_after={"wms.Warehouse": 1},
            missing_table_labels=("wms.MissingModel",),
        )

        lines = render_reset_summary(summary, heading="Reset")

        self.assertIn("Skipped missing tables:", lines)
        self.assertIn("- wms.MissingModel", lines)

    def test_existing_table_labels_reports_missing_tables(self):
        labels = ("wms.Warehouse", "wms.Location")

        with mock.patch(
            "wms.reset_operational_data.connection.introspection.table_names",
            return_value=[Warehouse._meta.db_table],
        ):
            present, missing = _existing_table_labels(labels)

        self.assertEqual(present, ("wms.Warehouse",))
        self.assertEqual(missing, ("wms.Location",))

    def test_validate_configuration_rejects_duplicate_labels(self):
        with (
            mock.patch(
                "wms.reset_operational_data.KEEP_MODEL_LABELS",
                frozenset({"wms.Warehouse"}),
            ),
            mock.patch(
                "wms.reset_operational_data.DELETE_BATCHES",
                (("dup", ("wms.Warehouse",)),),
            ),
            mock.patch(
                "wms.reset_operational_data._all_known_model_labels",
                return_value={"wms.Warehouse"},
            ),
        ):
            with self.assertRaisesMessage(ValueError, "both keep and delete"):
                _validate_configuration()

    def test_validate_configuration_rejects_missing_labels(self):
        with (
            mock.patch("wms.reset_operational_data.KEEP_MODEL_LABELS", frozenset()),
            mock.patch("wms.reset_operational_data.DELETE_BATCHES", ()),
            mock.patch(
                "wms.reset_operational_data._all_known_model_labels",
                return_value={"wms.Warehouse"},
            ),
        ):
            with self.assertRaisesMessage(ValueError, "missing model labels"):
                _validate_configuration()

    def test_validate_configuration_rejects_unknown_labels(self):
        with (
            mock.patch(
                "wms.reset_operational_data.KEEP_MODEL_LABELS",
                frozenset({"wms.UnknownModel"}),
            ),
            mock.patch("wms.reset_operational_data.DELETE_BATCHES", ()),
            mock.patch(
                "wms.reset_operational_data._all_known_model_labels",
                return_value=set(),
            ),
        ):
            with self.assertRaisesMessage(ValueError, "references unknown model labels"):
                _validate_configuration()

    def test_reset_operational_data_apply_raises_when_deleted_rows_remain(self):
        model_mock = mock.Mock()

        with (
            mock.patch("wms.reset_operational_data._validate_configuration"),
            mock.patch(
                "wms.reset_operational_data._existing_table_labels",
                side_effect=[
                    (("wms.Contact",), ()),
                    (("wms.Warehouse",), ()),
                ],
            ),
            mock.patch(
                "wms.reset_operational_data._count_labels",
                side_effect=[
                    {"wms.Warehouse": 1},
                    {"wms.Contact": 1},
                    {"wms.Warehouse": 1},
                    {"wms.Contact": 1},
                ],
            ),
            mock.patch(
                "wms.reset_operational_data._resolve_model",
                return_value=model_mock,
            ),
        ):
            with self.assertRaisesMessage(ValueError, "still has 1 row"):
                reset_operational_data(apply=True)

    def test_reset_operational_data_apply_raises_when_preserved_rows_change(self):
        model_mock = mock.Mock()

        with (
            mock.patch("wms.reset_operational_data._validate_configuration"),
            mock.patch(
                "wms.reset_operational_data._existing_table_labels",
                side_effect=[
                    (("wms.Contact",), ()),
                    (("wms.Warehouse",), ()),
                ],
            ),
            mock.patch(
                "wms.reset_operational_data._count_labels",
                side_effect=[
                    {"wms.Warehouse": 1},
                    {"wms.Contact": 1},
                    {"wms.Warehouse": 2},
                    {"wms.Contact": 0},
                ],
            ),
            mock.patch(
                "wms.reset_operational_data._resolve_model",
                return_value=model_mock,
            ),
        ):
            with self.assertRaisesMessage(ValueError, "Preserved model wms.Warehouse changed"):
                reset_operational_data(apply=True)
