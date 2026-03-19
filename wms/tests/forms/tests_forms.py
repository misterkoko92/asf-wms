from unittest import mock

from django import forms as django_forms
from django.test import TestCase
from django.utils import timezone, translation

from contacts.correspondent_recipient_promotion import SUPPORT_ORGANIZATION_NAME
from contacts.models import Contact, ContactAddress, ContactType
from wms.forms import (
    AdjustStockForm,
    PackCartonForm,
    ScanOrderSelectForm,
    ScanPackForm,
    ScanReceiptAssociationForm,
    ScanReceiptCreateForm,
    ScanReceiptPalletForm,
    ScanReceiptSelectForm,
    ScanShipmentForm,
    ScanStockUpdateForm,
    ShipmentTrackingForm,
    _select_single_choice,
)
from wms.models import (
    Carton,
    CartonStatus,
    Destination,
    Order,
    OrganizationRole,
    OrganizationRoleAssignment,
    Product,
    Receipt,
    ReceiptType,
    RecipientBinding,
    Shipment,
    ShipmentStatus,
    ShipperScope,
    Warehouse,
)


class FormsTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="WH-FORMS")
        self.product = Product.objects.create(name="Produit Test")

    def _create_contact(self, name, *, country=None):
        contact = Contact.objects.create(name=name)
        if country:
            ContactAddress.objects.create(
                contact=contact,
                address_line1=f"{name} addr",
                country=country,
                is_default=True,
            )
        return contact

    def _create_org(self, name):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, name, *, organization=None):
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=name.split()[0],
            last_name=name.split()[-1],
            organization=organization,
            is_active=True,
        )

    def _activate_shipper(self, organization, *, destination=None, all_destinations=False):
        assignment = OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        if destination is not None or all_destinations:
            ShipperScope.objects.create(
                role_assignment=assignment,
                destination=destination,
                all_destinations=all_destinations,
                is_active=True,
            )
        return assignment

    def _activate_recipient(self, organization):
        return OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )

    def _bind_recipient(self, *, shipper_org, recipient_org, destination):
        return RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

    def _create_shipment(self, suffix, *, status=ShipmentStatus.DRAFT):
        return Shipment.objects.create(
            reference=f"SHP-{suffix}",
            status=status,
            shipper_name=f"Shipper {suffix}",
            recipient_name=f"Recipient {suffix}",
            destination_address="1 Rue Test",
            destination_country="France",
        )

    def test_adjust_stock_form_rejects_zero_delta(self):
        form = AdjustStockForm(data={"quantity_delta": "0"})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["quantity_delta"], ["La quantité doit être non nulle."])

    def test_adjust_stock_form_clean_quantity_delta_accepts_non_zero(self):
        form = AdjustStockForm()
        form.cleaned_data = {"quantity_delta": 2}

        self.assertEqual(form.clean_quantity_delta(), 2)

    def test_pack_carton_form_init_excludes_shipped_entities(self):
        carton_kept = Carton.objects.create(code="CT-KEEP")
        carton_shipped = Carton.objects.create(code="CT-SHIPPED", status=CartonStatus.SHIPPED)
        shipment_kept = self._create_shipment("KEEP", status=ShipmentStatus.DRAFT)
        shipment_archived = self._create_shipment("ARCHIVE", status=ShipmentStatus.DRAFT)
        Shipment.objects.filter(pk=shipment_archived.pk).update(archived_at=timezone.now())
        shipment_shipped = self._create_shipment("SHIPPED", status=ShipmentStatus.SHIPPED)
        shipment_delivered = self._create_shipment("DELIV", status=ShipmentStatus.DELIVERED)

        form = PackCartonForm()

        carton_ids = set(form.fields["carton"].queryset.values_list("id", flat=True))
        shipment_ids = set(form.fields["shipment"].queryset.values_list("id", flat=True))
        self.assertIn(carton_kept.id, carton_ids)
        self.assertNotIn(carton_shipped.id, carton_ids)
        self.assertIn(shipment_kept.id, shipment_ids)
        self.assertNotIn(shipment_archived.id, shipment_ids)
        self.assertNotIn(shipment_shipped.id, shipment_ids)
        self.assertNotIn(shipment_delivered.id, shipment_ids)

    def test_pack_carton_form_rejects_carton_and_carton_code_together(self):
        carton = Carton.objects.create(code="CT-VALID")
        form = PackCartonForm(
            data={
                "product": str(self.product.id),
                "quantity": "2",
                "carton": str(carton.id),
                "carton_code": "CT-NEW",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.non_field_errors(),
            ["Sélectionnez un carton existant ou indiquez un code, pas les deux."],
        )

    def test_pack_carton_form_accepts_single_carton_source(self):
        carton = Carton.objects.create(code="CT-VALID-ONLY")
        form = PackCartonForm(
            data={
                "product": str(self.product.id),
                "quantity": "2",
                "carton": str(carton.id),
                "carton_code": "",
            }
        )

        self.assertTrue(form.is_valid())

    def test_scan_pack_form_exposes_active_preassigned_destinations(self):
        correspondent = Contact.objects.create(name="Correspondent")
        active_destination = Destination.objects.create(
            city="Nouakchott",
            iata_code="NKC",
            country="Mauritanie",
            correspondent_contact=correspondent,
            is_active=True,
        )
        Destination.objects.create(
            city="Inactive",
            iata_code="INA",
            country="France",
            correspondent_contact=correspondent,
            is_active=False,
        )

        form = ScanPackForm()

        destination_ids = set(
            form.fields["preassigned_destination"].queryset.values_list("id", flat=True)
        )
        self.assertEqual(destination_ids, {active_destination.id})

    def test_scan_receipt_select_form_orders_unsliced_queryset(self):
        receipt_b = Receipt.objects.create(reference="B-RECEIPT", warehouse=self.warehouse)
        receipt_a = Receipt.objects.create(reference="A-RECEIPT", warehouse=self.warehouse)

        form = ScanReceiptSelectForm(
            receipts_qs=Receipt.objects.filter(id__in=[receipt_b.id, receipt_a.id])
        )

        refs = list(form.fields["receipt"].queryset.values_list("reference", flat=True))
        self.assertEqual(refs, ["A-RECEIPT", "B-RECEIPT"])

    def test_scan_receipt_create_form_requires_receipt_type(self):
        form = ScanReceiptCreateForm(
            data={
                "receipt_type": "",
                "warehouse": str(self.warehouse.id),
                "received_on": "2026-02-01",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["receipt_type"], ["Type de réception requis."])

    def test_scan_receipt_forms_translate_labels_and_errors_in_english(self):
        with translation.override("en"):
            create_form = ScanReceiptCreateForm(
                data={
                    "receipt_type": ReceiptType.PALLET,
                    "warehouse": "",
                    "received_on": "",
                }
            )

            self.assertEqual(create_form.fields["receipt_type"].label, "Receipt type")
            self.assertEqual(create_form.fields["source_contact"].label, "Source")
            self.assertFalse(create_form.is_valid())
            self.assertEqual(create_form.errors["source_contact"], ["Source is required."])
            self.assertEqual(create_form.errors["carrier_contact"], ["Carrier is required."])
            self.assertEqual(create_form.errors["warehouse"], ["Warehouse is required."])

            pallet_form = ScanReceiptPalletForm()
            self.assertEqual(pallet_form.fields["received_on"].label, "Reception date")
            self.assertEqual(pallet_form.fields["pallet_count"].label, "Number of pallets")

    def test_scan_receipt_create_form_requires_pallet_contacts_and_warehouse_and_sets_default_date(
        self,
    ):
        form = ScanReceiptCreateForm(
            data={
                "receipt_type": ReceiptType.PALLET,
                "received_on": "",
                "warehouse": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["source_contact"], ["Provenance requise."])
        self.assertEqual(form.errors["carrier_contact"], ["Transporteur requis."])
        self.assertEqual(form.errors["warehouse"], ["Entrepôt requis."])
        self.assertEqual(form.cleaned_data.get("received_on"), timezone.localdate())

    def test_scan_receipt_and_stock_forms_use_active_org_role_assignments(self):
        donor = self._create_org("Donor Role")
        shipper = self._create_org("Shipper Role")
        transporter = self._create_org("Transporter Role")
        inactive_donor = self._create_org("Inactive Donor")
        legacy_contact = self._create_org("Legacy Only")
        self._activate_recipient(legacy_contact)
        OrganizationRoleAssignment.objects.create(
            organization=donor,
            role=OrganizationRole.DONOR,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=transporter,
            role=OrganizationRole.TRANSPORTER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=inactive_donor,
            role=OrganizationRole.DONOR,
            is_active=False,
        )

        create_form = ScanReceiptCreateForm()
        pallet_form = ScanReceiptPalletForm()
        association_form = ScanReceiptAssociationForm()
        stock_form = ScanStockUpdateForm()

        self.assertEqual(list(create_form.fields["source_contact"].queryset), [donor, shipper])
        self.assertEqual(list(create_form.fields["carrier_contact"].queryset), [transporter])
        self.assertEqual(list(pallet_form.fields["source_contact"].queryset), [donor])
        self.assertEqual(list(pallet_form.fields["carrier_contact"].queryset), [transporter])
        self.assertEqual(list(association_form.fields["source_contact"].queryset), [shipper])
        self.assertEqual(
            list(association_form.fields["carrier_contact"].queryset),
            [transporter],
        )
        self.assertEqual(list(stock_form.fields["donor_contact"].queryset), [donor])
        self.assertNotIn(legacy_contact, create_form.fields["source_contact"].queryset)
        self.assertNotIn(inactive_donor, pallet_form.fields["source_contact"].queryset)

    def test_scan_stock_update_form_reports_missing_product(self):
        with mock.patch("wms.forms.resolve_product", return_value=None):
            form = ScanStockUpdateForm(
                data={
                    "product_code": "UNKNOWN",
                    "quantity": "1",
                    "expires_on": "2026-03-01",
                }
            )
            self.assertFalse(form.is_valid())

        self.assertEqual(form.errors["product_code"], ["Produit introuvable."])

    def test_scan_shipment_form_init_handles_destination_without_correspondent(self):
        fake_destination = mock.Mock(spec=Destination)
        fake_destination.correspondent_contact_id = None

        with mock.patch.object(
            ScanShipmentForm,
            "_resolve_selected_destination",
            return_value=fake_destination,
        ):
            with mock.patch(
                "wms.forms.recipient_contacts_for_destination",
                return_value=Contact.objects.none(),
            ):
                with mock.patch(
                    "wms.forms.eligible_correspondent_contacts_for_destination",
                    return_value=Contact.objects.none(),
                ):
                    form = ScanShipmentForm(destination_id="123")

        self.assertEqual(form.fields["correspondent_contact"].queryset.count(), 0)

    def test_scan_shipment_form_init_lists_active_shipper_for_destination(self):
        correspondent = self._create_contact("Correspondent Form")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR-ACC",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_org("Shipper Active")
        self._activate_shipper(shipper, destination=destination)

        form = ScanShipmentForm(destination_id=str(destination.id))

        self.assertIn(
            shipper.id,
            form.fields["shipper_contact"].queryset.values_list("id", flat=True),
        )

    def test_scan_shipment_form_init_auto_selects_single_correspondent_when_unbound(self):
        correspondent = self._create_contact("Correspondent Auto")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR-AUTO",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Auto")
        self._activate_shipper(shipper, destination=destination)

        form = ScanShipmentForm(destination_id=str(destination.id))

        self.assertEqual(form.fields["correspondent_contact"].initial, correspondent.id)

    def test_scan_shipment_form_init_keeps_destination_correspondent_without_tag(self):
        correspondent = self._create_contact("Correspondent Untagged")
        destination = Destination.objects.create(
            city="Dakar",
            iata_code="DKR-AUTO",
            country="Senegal",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Dakar")
        self._activate_shipper(shipper, destination=destination)

        form = ScanShipmentForm(destination_id=str(destination.id))

        self.assertEqual(
            list(form.fields["correspondent_contact"].queryset.values_list("id", flat=True)),
            [correspondent.id],
        )
        self.assertEqual(form.fields["correspondent_contact"].initial, correspondent.id)

    def test_scan_shipment_form_init_without_destination_hides_contact_selectors(self):
        global_shipper = self._create_contact("Global Shipper")
        self._activate_shipper(global_shipper)
        global_recipient = self._create_contact("Global Recipient")
        self._activate_recipient(global_recipient)
        scoped_destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV2",
            country="Rep. du Congo",
            correspondent_contact=self._create_contact("Scoped Corr"),
            is_active=True,
        )
        scoped_shipper = self._create_contact("Scoped Shipper")
        self._activate_shipper(scoped_shipper, destination=scoped_destination)
        scoped_recipient = self._create_contact("Scoped Recipient")
        self._activate_recipient(scoped_recipient)

        form = ScanShipmentForm()

        self.assertEqual(form.fields["shipper_contact"].queryset.count(), 0)
        self.assertEqual(form.fields["recipient_contact"].queryset.count(), 0)
        self.assertEqual(form.fields["correspondent_contact"].queryset.count(), 0)

    def test_scan_shipment_form_init_filters_recipients_for_selected_shipper(
        self,
    ):
        correspondent = self._create_contact("Correspondent Shipper")
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ1",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper_a = self._create_org("Shipper A")
        shipper_b = self._create_org("Shipper B")
        recipient_allowed = self._create_org("Recipient Allowed")
        recipient_other = self._create_org("Recipient Other")
        self._activate_shipper(shipper_a, destination=destination)
        self._activate_shipper(shipper_b, destination=destination)
        self._activate_recipient(recipient_allowed)
        self._activate_recipient(recipient_other)
        self._bind_recipient(
            shipper_org=shipper_a,
            recipient_org=recipient_allowed,
            destination=destination,
        )
        self._bind_recipient(
            shipper_org=shipper_b,
            recipient_org=recipient_other,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_a.id),
            },
            destination_id=str(destination.id),
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        self.assertIn(recipient_allowed.id, recipient_ids)
        self.assertNotIn(recipient_other.id, recipient_ids)

    def test_scan_shipment_form_excludes_people_without_organization_from_shipper_and_recipient(
        self,
    ):
        correspondent = self._create_contact("Correspondent Struct")
        destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW-STRUCT",
            country="Togo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper_org = self._create_org("Shipper Org")
        shipper_person_with_org = self._create_person(
            "Jean Dupont",
            organization=shipper_org,
        )
        shipper_person_no_org = self._create_person("Paul Martin")

        recipient_org = self._create_org("Recipient Org")
        recipient_person_with_org = self._create_person(
            "Alice Yao",
            organization=recipient_org,
        )
        recipient_person_no_org = self._create_person("Lea Ndiaye")
        self._activate_shipper(shipper_org, destination=destination)
        self._activate_recipient(recipient_org)
        self._bind_recipient(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_org.id),
            },
            destination_id=str(destination.id),
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))

        self.assertIn(shipper_org.id, shipper_ids)
        self.assertIn(shipper_person_with_org.id, shipper_ids)
        self.assertNotIn(shipper_person_no_org.id, shipper_ids)

        self.assertIn(recipient_org.id, recipient_ids)
        self.assertIn(recipient_person_with_org.id, recipient_ids)
        self.assertNotIn(recipient_person_no_org.id, recipient_ids)

    def test_scan_shipment_form_init_does_not_auto_select_single_choices(self):
        correspondent = self._create_contact("Correspondent Seq")
        destination = Destination.objects.create(
            city="Maroantsetra",
            iata_code="WMN",
            country="Madagascar",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Seq")
        self._activate_shipper(shipper, destination=destination)
        recipient = self._create_org("Recipient Seq")
        self._activate_recipient(recipient)
        self._bind_recipient(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={"destination": str(destination.id)},
            destination_id=str(destination.id),
        )

        self.assertIsNone(form.fields["shipper_contact"].initial)
        self.assertIsNone(form.fields["recipient_contact"].initial)
        self.assertIsNone(form.fields["correspondent_contact"].initial)

    def test_scan_shipment_form_labels_include_contact_details_for_organization_contacts(self):
        shipper_org = Contact.objects.create(
            name="ASSOCIATION TEST",
            contact_type=ContactType.ORGANIZATION,
        )
        correspondent = self._create_contact("Correspondent Labels")
        destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV-LABEL",
            country="Rep. du Congo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = Contact.objects.create(
            name="Legacy Shipper Name",
            contact_type=ContactType.PERSON,
            title="M.",
            first_name="Jean",
            last_name="Dupont",
            organization=shipper_org,
        )
        self._activate_shipper(shipper_org, destination=destination)
        recipient_org = Contact.objects.create(
            name="Recipient Org Labels",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self._activate_recipient(recipient_org)
        self._bind_recipient(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
        )
        recipient = Contact.objects.create(
            name="Legacy Recipient Name",
            contact_type=ContactType.PERSON,
            title="Mme",
            first_name="Alice",
            last_name="Martin",
            organization=recipient_org,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_org.id),
            },
            destination_id=str(destination.id),
        )

        shipper_label = form.fields["shipper_contact"].label_from_instance(shipper)
        recipient_label = form.fields["recipient_contact"].label_from_instance(recipient)
        self.assertEqual(shipper_label, "ASSOCIATION TEST (M., Jean, DUPONT)")
        self.assertEqual(recipient_label, "Recipient Org Labels (Mme, Alice, MARTIN)")

    def test_scan_shipment_form_labels_correspondent_recipients_with_iata_context(self):
        destination = Destination.objects.create(
            city="Bangui",
            iata_code="BGF",
            country="Centrafrique",
            correspondent_contact=self._create_contact("Correspondent BGF"),
            is_active=True,
        )
        shipper_org = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self._activate_shipper(shipper_org, destination=destination)

        support_org = Contact.objects.create(
            name=SUPPORT_ORGANIZATION_NAME,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self._activate_recipient(support_org)
        self._bind_recipient(
            shipper_org=shipper_org,
            recipient_org=support_org,
            destination=destination,
        )
        recipient = Contact.objects.create(
            name="Christian Limbio",
            contact_type=ContactType.PERSON,
            first_name="Christian",
            last_name="Limbio",
            organization=support_org,
            is_active=True,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_org.id),
            },
            destination_id=str(destination.id),
        )

        recipient_label = form.fields["recipient_contact"].label_from_instance(recipient)
        self.assertEqual(
            recipient_label,
            "ASF - CORRESPONDANT - BGF (Christian LIMBIO)",
        )

    def test_scan_shipment_form_clean_rejects_shipper_out_of_scope_even_if_selectable(self):
        expected_correspondent = self._create_contact("Corr Expected")
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR1",
            country="France",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        other_destination = Destination.objects.create(
            city="Lyon",
            iata_code="LYN1",
            country="France",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper_wrong = self._create_org("Shipper Wrong")
        self._activate_shipper(shipper_wrong, destination=other_destination)
        recipient_ok = self._create_org("Recipient OK")
        self._activate_recipient(recipient_ok)
        self._bind_recipient(
            shipper_org=shipper_wrong,
            recipient_org=recipient_ok,
            destination=other_destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_wrong.id),
                "recipient_contact": str(recipient_ok.id),
                "correspondent_contact": str(expected_correspondent.id),
                "carton_count": "1",
            }
        )
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertFalse(form.is_valid())
        self.assertTrue(
            any(
                "escale" in error.lower() or "destination" in error.lower()
                for error in form.errors.get("shipper_contact", [])
            )
        )

    def test_scan_shipment_form_clean_accepts_scoped_shipper_with_bound_recipient(self):
        expected_correspondent = self._create_contact("Corr Multi")
        destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV1",
            country="Rep. du Congo",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper = self._create_org("Shipper Multi")
        self._activate_shipper(shipper, destination=destination)
        recipient = self._create_org("Recipient Multi")
        ContactAddress.objects.create(
            contact=recipient,
            address_line1="Recipient Multi addr",
            country="Rep. du Congo",
            is_default=True,
        )
        self._activate_recipient(recipient)
        self._bind_recipient(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
                "recipient_contact": str(recipient.id),
                "correspondent_contact": str(expected_correspondent.id),
                "carton_count": "1",
            }
        )
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertTrue(form.is_valid())

    def test_scan_shipment_form_clean_accepts_bound_recipient_without_country_match(self):
        expected_correspondent = self._create_contact("Corr Expected 2")
        destination = Destination.objects.create(
            city="Marseille",
            iata_code="MRS1",
            country="France",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper_ok = self._create_org("Shipper OK")
        self._activate_shipper(shipper_ok, destination=destination)
        recipient_wrong_country = self._create_org("Recipient Wrong")
        ContactAddress.objects.create(
            contact=recipient_wrong_country,
            address_line1="Recipient Wrong addr",
            country="Belgique",
            is_default=True,
        )
        self._activate_recipient(recipient_wrong_country)
        self._bind_recipient(
            shipper_org=shipper_ok,
            recipient_org=recipient_wrong_country,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_ok.id),
                "recipient_contact": str(recipient_wrong_country.id),
                "correspondent_contact": str(expected_correspondent.id),
                "carton_count": "1",
            }
        )
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertTrue(form.is_valid())

    def test_scan_shipment_form_clean_accepts_bound_recipient(self):
        expected_correspondent = self._create_contact("Corr Expected 4")
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA1",
            country="Cameroun",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper = self._create_org("Shipper Linked")
        self._activate_shipper(shipper, destination=destination)
        recipient = self._create_org("Recipient Linked")
        self._activate_recipient(recipient)
        self._bind_recipient(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
                "recipient_contact": str(recipient.id),
                "correspondent_contact": str(expected_correspondent.id),
                "carton_count": "1",
            }
        )
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertTrue(form.is_valid())

    def test_scan_shipment_form_clean_rejects_unlinked_correspondent(self):
        expected_correspondent = self._create_contact("Corr Expected 3")
        destination = Destination.objects.create(
            city="Nice",
            iata_code="NCE1",
            country="France",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper_ok = self._create_contact("Shipper OK 2")
        recipient_ok = self._create_contact("Recipient OK 2", country="France")
        other_correspondent = self._create_contact("Corr Other")

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_ok.id),
                "recipient_contact": str(recipient_ok.id),
                "correspondent_contact": str(other_correspondent.id),
                "carton_count": "1",
            }
        )
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["correspondent_contact"], ["Correspondant non lie a la destination."]
        )

    def test_scan_shipment_form_invalid_choice_explains_recipient_person_without_organization(
        self,
    ):
        correspondent = self._create_contact("Corr Invalid Recipient")
        destination = Destination.objects.create(
            city="Lome",
            iata_code="LFW-INV",
            country="Togo",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Valid")
        self._activate_shipper(shipper, destination=destination)
        recipient_without_org = Contact.objects.create(
            name="Recipient Person",
            contact_type=ContactType.PERSON,
            first_name="Lea",
            last_name="Martin",
            is_active=True,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
                "recipient_contact": str(recipient_without_org.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["recipient_contact"],
            ["Destinataire invalide: ce contact est un particulier sans organisation."],
        )

    def test_scan_shipment_form_init_keeps_other_shippers_available_for_grouped_select(self):
        correspondent = self._create_contact("Corr Invalid Link")
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA-INV",
            country="Cameroun",
            correspondent_contact=correspondent,
            is_active=True,
        )
        other_destination = Destination.objects.create(
            city="Bafoussam",
            iata_code="BFX-INV",
            country="Cameroun",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper_a = self._create_org("Shipper A Invalid Link")
        self._activate_shipper(shipper_a, destination=other_destination)

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_a.id),
                "carton_count": "1",
            }
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        self.assertIn(shipper_a.id, shipper_ids)

    def test_shipment_tracking_form_uses_first_choice_for_unknown_initial(self):
        form = ShipmentTrackingForm(initial_status="unknown-status")

        self.assertEqual(form.fields["status"].initial, form.fields["status"].choices[0][0])

    def test_shipment_tracking_form_filters_status_choices(self):
        form = ShipmentTrackingForm(
            allowed_statuses=["planning_ok", "planned"],
            initial_status="planned",
        )

        self.assertEqual(
            [choice[0] for choice in form.fields["status"].choices],
            ["planning_ok", "planned"],
        )
        self.assertEqual(form.fields["status"].initial, "planned")

    def test_select_single_choice_returns_when_queryset_is_none(self):
        field = django_forms.ModelChoiceField(queryset=Contact.objects.none(), required=False)
        field._queryset = None

        _select_single_choice(field)

        self.assertIsNone(field.initial)

    def test_scan_order_select_form_orders_unsliced_queryset(self):
        order_b = Order.objects.create(
            reference="B-ORDER",
            shipper_name="Shipper B",
            recipient_name="Recipient B",
            destination_address="1 Rue B",
        )
        order_a = Order.objects.create(
            reference="A-ORDER",
            shipper_name="Shipper A",
            recipient_name="Recipient A",
            destination_address="1 Rue A",
        )

        form = ScanOrderSelectForm(orders_qs=Order.objects.filter(id__in=[order_b.id, order_a.id]))

        refs = list(form.fields["order"].queryset.values_list("reference", flat=True))
        self.assertEqual(refs, ["A-ORDER", "B-ORDER"])
