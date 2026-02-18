from types import SimpleNamespace
from unittest import mock

from django import forms as django_forms
from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactAddress, ContactTag
from wms.forms import (
    AdjustStockForm,
    PackCartonForm,
    ScanOrderSelectForm,
    ScanReceiptCreateForm,
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
    Product,
    Receipt,
    ReceiptType,
    Shipment,
    ShipmentStatus,
    Warehouse,
)


class FormsTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="WH-FORMS")
        self.product = Product.objects.create(name="Produit Test")

    def _create_contact(self, name, *, destination=None, country=None):
        contact = Contact.objects.create(name=name)
        if destination:
            contact.destinations.add(destination)
        if country:
            ContactAddress.objects.create(
                contact=contact,
                address_line1=f"{name} addr",
                country=country,
                is_default=True,
            )
        return contact

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
        shipment_shipped = self._create_shipment("SHIPPED", status=ShipmentStatus.SHIPPED)
        shipment_delivered = self._create_shipment("DELIV", status=ShipmentStatus.DELIVERED)

        form = PackCartonForm()

        carton_ids = set(form.fields["carton"].queryset.values_list("id", flat=True))
        shipment_ids = set(form.fields["shipment"].queryset.values_list("id", flat=True))
        self.assertIn(carton_kept.id, carton_ids)
        self.assertNotIn(carton_shipped.id, carton_ids)
        self.assertIn(shipment_kept.id, shipment_ids)
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

    def test_scan_receipt_select_form_orders_unsliced_queryset(self):
        receipt_b = Receipt.objects.create(reference="B-RECEIPT", warehouse=self.warehouse)
        receipt_a = Receipt.objects.create(reference="A-RECEIPT", warehouse=self.warehouse)

        form = ScanReceiptSelectForm(receipts_qs=Receipt.objects.filter(id__in=[receipt_b.id, receipt_a.id]))

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
        original_first = QuerySet.first
        fake_destination = SimpleNamespace(country="France", correspondent_contact_id=None)

        def first_side_effect(queryset, *args, **kwargs):
            if getattr(queryset, "model", None) is Destination:
                return fake_destination
            return original_first(queryset, *args, **kwargs)

        with mock.patch(
            "django.db.models.query.QuerySet.first",
            autospec=True,
            side_effect=first_side_effect,
        ):
            with mock.patch(
                "wms.forms.filter_contacts_for_destination",
                side_effect=lambda queryset, _destination: queryset,
            ):
                form = ScanShipmentForm(destination_id="123")

        self.assertEqual(form.fields["correspondent_contact"].queryset.count(), 0)

    def test_scan_shipment_form_init_matches_accented_shipper_tag(self):
        correspondent = self._create_contact("Correspondent Form")
        correspondent_tag = ContactTag.objects.create(name="correspondant")
        correspondent.tags.add(correspondent_tag)
        destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR-ACC",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Accent")
        shipper_tag = ContactTag.objects.create(name="expéditeur")
        shipper.tags.add(shipper_tag)
        recipient = self._create_contact("Recipient Form", country="France")
        recipient_tag = ContactTag.objects.create(name="destinataire")
        recipient.tags.add(recipient_tag)

        form = ScanShipmentForm(destination_id=str(destination.id))

        self.assertIn(
            shipper.id,
            form.fields["shipper_contact"].queryset.values_list("id", flat=True),
        )

    def test_scan_shipment_form_init_without_destination_hides_contact_selectors(self):
        global_shipper = self._create_contact("Global Shipper")
        shipper_tag = ContactTag.objects.create(name="expediteur")
        global_shipper.tags.add(shipper_tag)
        global_recipient = self._create_contact("Global Recipient")
        recipient_tag = ContactTag.objects.create(name="destinataire")
        global_recipient.tags.add(recipient_tag)
        scoped_destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV2",
            country="Rep. du Congo",
            correspondent_contact=self._create_contact("Scoped Corr"),
            is_active=True,
        )
        scoped_shipper = self._create_contact("Scoped Shipper")
        scoped_shipper.tags.add(shipper_tag)
        scoped_shipper.destinations.add(scoped_destination)
        scoped_recipient = self._create_contact("Scoped Recipient")
        scoped_recipient.tags.add(recipient_tag)
        scoped_recipient.destinations.add(scoped_destination)

        form = ScanShipmentForm()

        self.assertEqual(form.fields["shipper_contact"].queryset.count(), 0)
        self.assertEqual(form.fields["recipient_contact"].queryset.count(), 0)
        self.assertEqual(form.fields["correspondent_contact"].queryset.count(), 0)

    def test_scan_shipment_form_init_filters_recipients_by_selected_shipper(self):
        correspondent = self._create_contact("Correspondent Shipper")
        correspondent_tag = ContactTag.objects.create(name="correspondant")
        correspondent.tags.add(correspondent_tag)
        destination = Destination.objects.create(
            city="Abidjan",
            iata_code="ABJ1",
            country="Cote d'Ivoire",
            correspondent_contact=correspondent,
            is_active=True,
        )
        shipper_tag = ContactTag.objects.create(name="expediteur")
        shipper_a = self._create_contact("Shipper A")
        shipper_a.tags.add(shipper_tag)
        shipper_a.destinations.add(destination)
        shipper_b = self._create_contact("Shipper B")
        shipper_b.tags.add(shipper_tag)
        shipper_b.destinations.add(destination)
        recipient_tag = ContactTag.objects.create(name="destinataire")
        global_recipient = self._create_contact("Recipient Global")
        global_recipient.tags.add(recipient_tag)
        linked_recipient = self._create_contact("Recipient Linked")
        linked_recipient.tags.add(recipient_tag)
        linked_recipient.linked_shippers.add(shipper_a)
        other_recipient = self._create_contact("Recipient Other")
        other_recipient.tags.add(recipient_tag)
        other_recipient.linked_shippers.add(shipper_b)

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_a.id),
            },
            destination_id=str(destination.id),
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        self.assertIn(global_recipient.id, recipient_ids)
        self.assertIn(linked_recipient.id, recipient_ids)
        self.assertNotIn(other_recipient.id, recipient_ids)

    def test_scan_shipment_form_clean_rejects_contact_for_other_destination(self):
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
        shipper_wrong = self._create_contact("Shipper Wrong")
        shipper_wrong.destinations.add(other_destination)
        recipient_ok = self._create_contact("Recipient OK", country="France")

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
        self.assertEqual(
            form.errors["shipper_contact"], ["Contact non disponible pour cette destination."]
        )

    def test_scan_shipment_form_clean_accepts_shipper_scoped_with_multi_destinations(self):
        expected_correspondent = self._create_contact("Corr Multi")
        destination = Destination.objects.create(
            city="Brazzaville",
            iata_code="BZV1",
            country="Rep. du Congo",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Multi")
        shipper.destinations.add(destination)
        recipient = self._create_contact("Recipient Multi", country="Rep. du Congo")

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

    def test_scan_shipment_form_clean_accepts_recipient_without_country_match(self):
        expected_correspondent = self._create_contact("Corr Expected 2")
        destination = Destination.objects.create(
            city="Marseille",
            iata_code="MRS1",
            country="France",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper_ok = self._create_contact("Shipper OK")
        recipient_wrong_country = self._create_contact("Recipient Wrong", country="Belgique")

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

    def test_scan_shipment_form_clean_rejects_recipient_not_linked_to_shipper(self):
        expected_correspondent = self._create_contact("Corr Expected 4")
        destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA1",
            country="Cameroun",
            correspondent_contact=expected_correspondent,
            is_active=True,
        )
        shipper = self._create_contact("Shipper Linked")
        shipper.destinations.add(destination)
        recipient = self._create_contact("Recipient Not Linked")
        recipient.linked_shippers.add(self._create_contact("Other Shipper"))

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

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["recipient_contact"],
            ["Destinataire non disponible pour cet expéditeur."],
        )

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

    def test_shipment_tracking_form_uses_first_choice_for_unknown_initial(self):
        form = ShipmentTrackingForm(initial_status="unknown-status")

        self.assertEqual(form.fields["status"].initial, form.fields["status"].choices[0][0])

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
