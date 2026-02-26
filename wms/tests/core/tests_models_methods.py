from datetime import date
from contextlib import nullcontext
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    AccountDocument,
    AccountDocumentType,
    AssociationProfile,
    AssociationRecipient,
    Carton,
    CartonFormat,
    CartonItem,
    Destination,
    Document,
    IntegrationDirection,
    IntegrationEvent,
    MovementType,
    Order,
    OrderDocument,
    OrderDocumentType,
    OrderLine,
    OrderReservation,
    PrintTemplate,
    PrintTemplateVersion,
    Product,
    ProductCategory,
    ProductKitItem,
    ProductLot,
    ProductTag,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    PublicOrderLink,
    RackColor,
    Receipt,
    ReceiptDonorSequence,
    ReceiptHorsFormat,
    ReceiptLine,
    ReceiptSequence,
    Shipment,
    ShipmentSequence,
    ShipmentStatus,
    ShipmentTrackingEvent,
    ShipmentTrackingStatus,
    StockMovement,
    Warehouse,
    WmsChange,
    generate_receipt_reference,
    generate_shipment_reference,
    normalize_reference_fragment,
)


class WmsModelMethodsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="models-user",
            password="pass1234",
        )
        self.contact = Contact.objects.create(
            name="Contact Org",
            contact_type=ContactType.ORGANIZATION,
        )
        self.warehouse = Warehouse.objects.create(name="Main Warehouse")
        self.location = self.warehouse.location_set.create(
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.product = Product.objects.create(
            sku="SKU-BASE",
            name="Base product",
            brand="BASE",
            default_location=self.location,
            qr_code_image="qr_codes/base.png",
        )
        self.destination = Destination.objects.create(
            city="Paris",
            iata_code="PAR",
            country="France",
            correspondent_contact=self.contact,
        )

    def _create_shipment(self, **overrides):
        data = {
            "reference": "260001",
            "shipper_name": "Shipper",
            "recipient_name": "Recipient",
            "correspondent_name": "Correspondent",
            "destination": self.destination,
            "destination_address": "10 Rue Test",
            "destination_country": "France",
        }
        data.update(overrides)
        return Shipment.objects.create(**data)

    def _create_order(self, **overrides):
        data = {
            "reference": "",
            "shipper_name": "Shipper",
            "recipient_name": "Recipient",
            "correspondent_name": "Correspondent",
            "destination_address": "10 Rue Test",
            "destination_country": "France",
        }
        data.update(overrides)
        return Order.objects.create(**data)

    def test_category_product_location_and_rack_methods(self):
        root = ProductCategory.objects.create(name="medical")
        child = ProductCategory.objects.create(name="epi", parent=root)
        self.assertEqual(str(child), "MEDICAL > EPI")

        child.name = "gants sterile"
        child.save(update_fields=["parent"])
        child.refresh_from_db()
        self.assertEqual(child.name, "Gants Sterile")

        tag = ProductTag.objects.create(name="froid")
        self.assertEqual(str(tag), "froid")

        self.assertEqual(str(self.product), "SKU-BASE - Base Product")

        no_sku_product = Product(name="No Sku")
        no_sku_product.generate_qr_code()
        self.assertFalse(bool(no_sku_product.qr_code_image))

        tax_product = Product(
            sku="SKU-TAX",
            name="Taxed",
            pu_ht=Decimal("10.00"),
            tva=Decimal("20.00"),
            qr_code_image="qr_codes/tax.png",
        )
        self.assertEqual(tax_product._compute_pu_ttc(), Decimal("12.00"))

        persisted_tax_product = Product.objects.create(
            sku="SKU-TAX-2",
            name="Taxed Persisted",
            pu_ht=Decimal("10.00"),
            tva=Decimal("0.2000"),
            qr_code_image="qr_codes/tax2.png",
        )
        Product.objects.filter(pk=persisted_tax_product.pk).update(
            tva=Decimal("20.0000")
        )
        persisted_tax_product.refresh_from_db()
        persisted_tax_product.save(update_fields=["name"])
        persisted_tax_product.refresh_from_db()
        self.assertEqual(persisted_tax_product.tva, Decimal("0.2000"))
        self.assertEqual(persisted_tax_product.pu_ttc, Decimal("12.00"))

        self.location.__class__.objects.filter(pk=self.location.pk).update(
            zone="a",
            aisle="b",
            shelf="c",
        )
        self.location.refresh_from_db()
        self.location.notes = "normalized"
        self.location.save(update_fields=["notes"])
        self.location.refresh_from_db()
        self.assertEqual((self.location.zone, self.location.aisle, self.location.shelf), ("A", "B", "C"))

        rack = RackColor.objects.create(
            warehouse=self.warehouse,
            zone="A",
            color="Blue",
        )
        self.assertEqual(str(rack), "Main Warehouse A - Blue")
        RackColor.objects.filter(pk=rack.pk).update(zone="a")
        rack.refresh_from_db()
        rack.color = "Green"
        rack.save(update_fields=["color"])
        rack.refresh_from_db()
        self.assertEqual(rack.zone, "A")

    def test_product_kit_item_clean_validations(self):
        kit = Product.objects.create(
            sku="KIT-1",
            name="Kit 1",
            qr_code_image="qr_codes/kit1.png",
        )
        component = Product.objects.create(
            sku="COMP-1",
            name="Component 1",
            qr_code_image="qr_codes/comp1.png",
        )

        same_item = ProductKitItem(kit=kit, component=kit, quantity=1)
        with self.assertRaisesMessage(
            ValidationError,
            "Un kit ne peut pas contenir le produit lui-meme.",
        ):
            same_item.clean()

        nested_kit = Product.objects.create(
            sku="KIT-2",
            name="Kit 2",
            qr_code_image="qr_codes/kit2.png",
        )
        ProductKitItem.objects.create(kit=nested_kit, component=component, quantity=1)
        valid_nested_component = ProductKitItem(kit=kit, component=nested_kit, quantity=1)
        valid_nested_component.clean()

        ProductKitItem.objects.create(kit=kit, component=nested_kit, quantity=1)
        invalid_cycle = ProductKitItem(kit=nested_kit, component=kit, quantity=1)
        with self.assertRaisesMessage(
            ValidationError,
            "Un kit ne peut pas contenir indirectement lui-meme.",
        ):
            invalid_cycle.clean()

    def test_receipt_and_related_repr_methods(self):
        lot = ProductLot.objects.create(
            product=self.product,
            lot_code="",
            quantity_on_hand=5,
            location=self.location,
        )
        self.assertIn("(lot)", str(lot))

        receipt = Receipt.objects.create(
            reference="REF-001",
            warehouse=self.warehouse,
            received_on=date(2026, 1, 1),
        )
        unsaved_receipt = Receipt(
            id=42,
            reference="",
            warehouse=self.warehouse,
            received_on=date(2026, 1, 1),
        )
        self.assertEqual(str(receipt), "REF-001")
        self.assertEqual(str(unsaved_receipt), "Receipt 42")

        line = ReceiptLine.objects.create(
            receipt=receipt,
            product=self.product,
            quantity=2,
            location=self.location,
        )
        self.assertIn("REF-001", str(line))
        self.assertFalse(line.is_received)
        line.received_lot = lot
        line.save(update_fields=["received_lot"])
        self.assertTrue(line.is_received)

        hors_format = ReceiptHorsFormat.objects.create(
            receipt=receipt,
            line_number=1,
            description="Hors format",
        )
        self.assertIn("Hors format 1", str(hors_format))

        sequence = ReceiptSequence.objects.create(year=2026, last_number=3)
        donor_sequence = ReceiptDonorSequence.objects.create(
            year=2026,
            donor=self.contact,
            last_number=2,
        )
        shipment_sequence = ShipmentSequence.objects.create(year=2026, last_number=9)
        self.assertEqual(str(sequence), "2026: 3")
        self.assertEqual(str(donor_sequence), "2026 Contact Org: 2")
        self.assertEqual(str(shipment_sequence), "2026: 9")

    def test_shipment_tracking_and_qr_methods(self):
        shipment = self._create_shipment(reference="260010")
        self.assertEqual(str(shipment), "260010")
        self.assertEqual(
            shipment.get_tracking_path(),
            reverse("scan:scan_shipment_track", args=[shipment.tracking_token]),
        )

        no_token = Shipment(
            tracking_token=None,
            reference="NO-TOKEN",
            shipper_name="S",
            recipient_name="R",
            destination_address="Address",
            destination_country="France",
        )
        self.assertEqual(no_token.get_tracking_path(), "")
        self.assertEqual(no_token.get_tracking_url(), "")
        no_token.generate_qr_code()
        self.assertFalse(bool(no_token.qr_code_image))

        with override_settings(SITE_BASE_URL="example.org"):
            url = shipment.get_tracking_url()
        self.assertTrue(url.startswith("https://example.org/"))

        shipment_no_qr = self._create_shipment(reference="260011")
        Shipment.objects.filter(pk=shipment_no_qr.pk).update(qr_code_image="")
        shipment_no_qr.refresh_from_db()

        def _fake_generate(*, request=None):
            shipment_no_qr.qr_code_image = "qr_codes/shipments/generated.png"

        with mock.patch.object(
            shipment_no_qr,
            "generate_qr_code",
            side_effect=_fake_generate,
        ) as generate_mock, mock.patch.object(shipment_no_qr, "save") as save_mock:
            shipment_no_qr.ensure_qr_code()
        generate_mock.assert_called_once_with(request=None)
        save_mock.assert_called_once_with(update_fields=["qr_code_image"])

        event = ShipmentTrackingEvent.objects.create(
            shipment=shipment,
            status=ShipmentTrackingStatus.PLANNED,
            actor_name="Agent",
            actor_structure="ASF",
        )
        self.assertIn("Planifié", str(event))

    def test_shipment_save_promotes_temp_reference_when_status_changes(self):
        shipment = self._create_shipment(
            reference="EXP-TEMP-01",
            status=ShipmentStatus.DRAFT,
        )

        shipment.notes = "Draft note"
        shipment.save(update_fields=["notes"])
        shipment.refresh_from_db()
        self.assertEqual(shipment.reference, "EXP-TEMP-01")

        shipment.status = ShipmentStatus.PICKING
        shipment.save(update_fields=["status"])
        shipment.refresh_from_db()
        self.assertFalse(shipment.reference.startswith("EXP-TEMP-"))
        self.assertTrue(shipment.reference.isdigit())
        self.assertEqual(len(shipment.reference), 6)

    def test_order_account_and_document_repr_methods(self):
        order = self._create_order(reference="")
        self.assertEqual(str(order), f"Order {order.id}")

        public_link = PublicOrderLink.objects.create(label="")
        self.assertIn("Lien commande", str(public_link))

        account_request = PublicAccountRequest.objects.create(
            association_name="Association A",
            email="a@example.org",
            address_line1="1 Rue A",
            status=PublicAccountRequestStatus.PENDING,
        )
        self.assertEqual(str(account_request), "Association A (Pending)")
        user_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.USER,
            association_name="wms-user",
            requested_username="wms-user",
            email="wms@example.org",
            status=PublicAccountRequestStatus.PENDING,
        )
        self.assertEqual(str(user_request), "Utilisateur wms-user (Pending)")

        profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            notification_emails="one@example.org\ntwo@example.org",
        )
        self.assertEqual(str(profile), f"{self.contact} - {self.user}")
        self.assertEqual(
            profile.get_notification_emails(),
            ["one@example.org", "two@example.org"],
        )

        recipient = AssociationRecipient.objects.create(
            association_contact=self.contact,
            name="Recipient A",
            address_line1="2 Rue B",
        )
        self.assertEqual(str(recipient), "Recipient A (Contact Org)")

        file_content = SimpleUploadedFile("doc.pdf", b"pdf-content")
        account_doc = AccountDocument.objects.create(
            association_contact=self.contact,
            account_request=account_request,
            doc_type=AccountDocumentType.STATUTES,
            file=file_content,
        )
        self.assertEqual(str(account_doc), "Statuts - pending")

        order_doc = OrderDocument.objects.create(
            order=order,
            doc_type=OrderDocumentType.INVOICE,
            file=SimpleUploadedFile("invoice.pdf", b"invoice"),
        )
        self.assertIn("Facture", str(order_doc))

        shipment = self._create_shipment(reference="260020")
        document = Document.objects.create(
            shipment=shipment,
            doc_type="additional",
        )
        self.assertIn("additional - 260020", str(document))

        template = PrintTemplate.objects.create(doc_type="shipment_note")
        version = PrintTemplateVersion.objects.create(
            template=template,
            version=1,
            layout={"a": 1},
        )
        self.assertEqual(str(template), "shipment_note")
        self.assertEqual(str(version), "shipment_note v1")

        change = WmsChange.objects.create(version=5)
        self.assertEqual(str(change), "WMS change v5")

        integration_event = IntegrationEvent.objects.create(
            direction=IntegrationDirection.OUTBOUND,
            source="wms.email",
            event_type="send_email",
        )
        self.assertEqual(str(integration_event), "wms.email:send_email (outbound)")

    def test_order_line_validation_and_carton_movement_repr(self):
        order = self._create_order(reference="ORD-001")

        invalid_line = OrderLine(
            order=order,
            product=self.product,
            quantity=2,
            reserved_quantity=3,
            prepared_quantity=4,
        )
        with self.assertRaises(ValidationError) as exc:
            invalid_line.clean()
        self.assertIn("reserved_quantity", exc.exception.message_dict)
        self.assertIn("prepared_quantity", exc.exception.message_dict)

        line = OrderLine.objects.create(
            order=order,
            product=self.product,
            quantity=5,
            reserved_quantity=1,
            prepared_quantity=2,
        )
        self.assertIn("ORD-001", str(line))
        self.assertEqual(line.remaining_quantity, 3)

        lot = ProductLot.objects.create(
            product=self.product,
            lot_code="LOT-001",
            quantity_on_hand=8,
            location=self.location,
        )
        reservation = OrderReservation.objects.create(
            order_line=line,
            product_lot=lot,
            quantity=1,
        )
        self.assertIn("LOT-001", str(reservation))

        carton_format = CartonFormat.objects.create(
            name="Format A",
            length_cm=Decimal("40.00"),
            width_cm=Decimal("30.00"),
            height_cm=Decimal("20.00"),
            max_weight_g=6000,
            is_default=True,
        )
        self.assertIn("Format A", str(carton_format))

        shipment = self._create_shipment(reference="260030")
        carton = Carton.objects.create(code="CART-1", shipment=shipment)
        self.assertEqual(str(carton), "CART-1")

        carton_item = CartonItem.objects.create(carton=carton, product_lot=lot, quantity=2)
        self.assertIn("CART-1", str(carton_item))

        movement = StockMovement.objects.create(
            movement_type=MovementType.OUT,
            product=self.product,
            product_lot=lot,
            quantity=2,
            from_location=self.location,
            related_carton=carton,
            related_shipment=shipment,
        )
        self.assertIn("out", str(movement))

    def test_association_recipient_save_normalizes_duplicated_fields(self):
        recipient = AssociationRecipient.objects.create(
            association_contact=self.contact,
            destination=self.destination,
            name="Legacy Name",
            structure_name="Structure Canonique",
            contact_title="mr",
            contact_last_name="Durand",
            contact_first_name="Marc",
            phones="+33600000000; +242061234567",
            emails="recipient@example.org; second@example.org",
            address_line1="10 Rue Test",
            city="Paris",
            country="France",
        )

        self.assertEqual(recipient.name, "Structure Canonique")
        self.assertEqual(recipient.phone, "+33600000000")
        self.assertEqual(recipient.email, "recipient@example.org")

    def test_reference_generation_branches_and_fragment_padding(self):
        self.assertEqual(normalize_reference_fragment("ab", 3), "ABX")

        with mock.patch("wms.models.timezone.localdate", return_value=date(2031, 1, 1)):
            existing_a = Receipt.objects.create(
                warehouse=self.warehouse,
                received_on=date(2031, 1, 1),
                source_contact=self.contact,
            )
            existing_b = Receipt.objects.create(
                warehouse=self.warehouse,
                received_on=date(2031, 1, 2),
                source_contact=self.contact,
            )
        Receipt.objects.filter(pk=existing_a.pk).update(reference="31-05-ABC-02")
        Receipt.objects.filter(pk=existing_b.pk).update(reference="31-07-ABC-04")
        ReceiptSequence.objects.filter(year=2031).delete()
        ReceiptDonorSequence.objects.filter(year=2031, donor=self.contact).delete()

        with mock.patch("wms.models.connection.features.has_select_for_update", True), mock.patch(
            "django.db.models.query.QuerySet.select_for_update",
            autospec=True,
            side_effect=lambda self, *args, **kwargs: self,
        ):
            receipt_ref = generate_receipt_reference(
                received_on=date(2031, 2, 1),
                source_contact=self.contact,
            )
        self.assertEqual(receipt_ref, "31-08-CON-05")

        with mock.patch("wms.models.timezone.localdate", return_value=date(2032, 1, 1)):
            shipment_a = self._create_shipment(reference="320123")
            shipment_b = self._create_shipment(reference="32ABCD")
        ShipmentSequence.objects.filter(year=2032).delete()
        Shipment.objects.filter(pk=shipment_b.pk).update(reference="320010")
        Shipment.objects.filter(pk=shipment_a.pk).update(reference="320123")

        with mock.patch("wms.models.timezone.localdate", return_value=date(2032, 1, 10)), mock.patch(
            "wms.models.connection.features.has_select_for_update",
            True,
        ), mock.patch(
            "django.db.models.query.QuerySet.select_for_update",
            autospec=True,
            side_effect=lambda self, *args, **kwargs: self,
        ):
            shipment_ref = generate_shipment_reference()
        self.assertEqual(shipment_ref, "320124")

    def test_generate_receipt_reference_handles_parse_and_integrity_races(self):
        class _FakeMatch:
            def __init__(self, seq, count):
                self._seq = seq
                self._count = count

            def group(self, name):
                if name == "seq":
                    return self._seq
                if name == "count":
                    return self._count
                raise KeyError(name)

        class _FakeRegex:
            def match(self, reference):
                if reference == "NO_MATCH":
                    return None
                if reference == "BAD_SEQ":
                    return _FakeMatch("bad", "2")
                if reference == "GOOD_SEQ":
                    return _FakeMatch("9", "2")
                if reference == "BAD_COUNT":
                    return _FakeMatch("9", "bad")
                if reference == "GOOD_DONOR":
                    return _FakeMatch("9", "7")
                return None

        sequence_missing_query = mock.Mock()
        sequence_missing_query.select_for_update.return_value = sequence_missing_query
        sequence_missing_query.get.side_effect = ReceiptSequence.DoesNotExist

        sequence = mock.Mock(last_number=9)
        sequence_existing_query = mock.Mock()
        sequence_existing_query.select_for_update.return_value = sequence_existing_query
        sequence_existing_query.get.return_value = sequence

        donor_missing_query = mock.Mock()
        donor_missing_query.select_for_update.return_value = donor_missing_query
        donor_missing_query.get.side_effect = ReceiptDonorSequence.DoesNotExist

        donor_sequence = mock.Mock(last_number=7)
        donor_existing_query = mock.Mock()
        donor_existing_query.select_for_update.return_value = donor_existing_query
        donor_existing_query.get.return_value = donor_sequence

        refs_query = mock.Mock()
        refs_query.values_list.return_value = ["NO_MATCH", "BAD_SEQ", "GOOD_SEQ"]
        donor_refs_query = mock.Mock()
        donor_refs_query.values_list.return_value = ["NO_MATCH", "BAD_COUNT", "GOOD_DONOR"]

        with mock.patch("wms.models.transaction.atomic", return_value=nullcontext()), mock.patch(
            "wms.models.connection.features.has_select_for_update",
            True,
        ), mock.patch(
            "wms.models.ReceiptSequence.objects.filter",
            side_effect=[sequence_missing_query, sequence_existing_query],
        ), mock.patch(
            "wms.models.ReceiptSequence.objects.create",
            side_effect=IntegrityError(),
        ), mock.patch(
            "wms.models.ReceiptDonorSequence.objects.filter",
            side_effect=[donor_missing_query, donor_existing_query],
        ), mock.patch(
            "wms.models.ReceiptDonorSequence.objects.create",
            side_effect=IntegrityError(),
        ), mock.patch(
            "wms.models.Receipt.objects.filter",
            side_effect=[refs_query, donor_refs_query],
        ), mock.patch(
            "wms.models.RECEIPT_REFERENCE_RE",
            _FakeRegex(),
        ):
            reference = generate_receipt_reference(
                received_on=date(2033, 1, 1),
                source_contact=self.contact,
            )

        self.assertEqual(reference, "33-10-CON-08")
        sequence.save.assert_called_once_with(update_fields=["last_number"])
        donor_sequence.save.assert_called_once_with(update_fields=["last_number"])

    def test_generate_shipment_reference_handles_integrity_race(self):
        sequence_missing_query = mock.Mock()
        sequence_missing_query.select_for_update.return_value = sequence_missing_query
        sequence_missing_query.get.side_effect = ShipmentSequence.DoesNotExist

        sequence = mock.Mock(last_number=123)
        sequence_existing_query = mock.Mock()
        sequence_existing_query.select_for_update.return_value = sequence_existing_query
        sequence_existing_query.get.return_value = sequence

        shipment_annotate_query = mock.Mock()
        shipment_filter_query = mock.Mock()
        shipment_order_query = mock.Mock()
        shipment_values_query = mock.Mock()
        shipment_values_query.first.return_value = "340123"
        shipment_order_query.values_list.return_value = shipment_values_query
        shipment_filter_query.order_by.return_value = shipment_order_query
        shipment_annotate_query.filter.return_value = shipment_filter_query

        with mock.patch("wms.models.transaction.atomic", return_value=nullcontext()), mock.patch(
            "wms.models.timezone.localdate",
            return_value=date(2034, 1, 1),
        ), mock.patch(
            "wms.models.connection.features.has_select_for_update",
            True,
        ), mock.patch(
            "wms.models.ShipmentSequence.objects.filter",
            side_effect=[sequence_missing_query, sequence_existing_query],
        ), mock.patch(
            "wms.models.ShipmentSequence.objects.create",
            side_effect=IntegrityError(),
        ), mock.patch(
            "wms.models.Shipment.objects.annotate",
            return_value=shipment_annotate_query,
        ):
            reference = generate_shipment_reference()

        self.assertEqual(reference, "340124")
        sequence.save.assert_called_once_with(update_fields=["last_number"])
