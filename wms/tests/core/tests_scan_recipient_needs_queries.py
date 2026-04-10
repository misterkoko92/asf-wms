from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms import models as wms_models
from wms.tests.core.tests_recipient_product_preferences import (
    RecipientProductPreferenceTestDataMixin,
)


class ScanRecipientNeedsQueriesTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self._lot_counter = 0
        self._shipment_counter = 0
        self._carton_counter = 0

        self.recipient_contact = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Alice",
            last_name="Recipient",
            organization=self.recipient_org_contact,
        )
        self.recipient_contact_link = wms_models.ShipmentRecipientContact.objects.create(
            recipient_organization=self.recipient_organization,
            contact=self.recipient_contact,
        )
        self.recipient_organization.validation_status = (
            wms_models.ShipmentValidationStatus.VALIDATED
        )
        self.recipient_organization.save(update_fields=["validation_status"])

        self.other_destination = wms_models.Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.other_recipient_org_contact = Contact.objects.create(
            name="Clinique Secondaire",
            contact_type=ContactType.ORGANIZATION,
        )
        self.other_recipient_organization = wms_models.ShipmentRecipientOrganization.objects.create(
            organization=self.other_recipient_org_contact,
            destination=self.other_destination,
            validation_status=wms_models.ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.other_recipient_contact = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Bruno",
            last_name="Second",
            organization=self.other_recipient_org_contact,
        )
        wms_models.ShipmentRecipientContact.objects.create(
            recipient_organization=self.other_recipient_organization,
            contact=self.other_recipient_contact,
        )

    def _helper_module(self):
        from wms.application.scan import recipient_needs_queries

        return recipient_needs_queries

    def _aware(self, year, month, day, hour=12, minute=0):
        return timezone.make_aware(
            datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )

    def _create_category(self, name, *, parent=None):
        return wms_models.ProductCategory.objects.create(name=name, parent=parent)

    def _create_product(self, sku, name, *, category):
        return wms_models.Product.objects.create(
            sku=sku,
            name=name,
            brand="ASF",
            qr_code_image=f"qr_codes/{sku.lower()}.png",
            category=category,
            is_active=True,
        )

    def _create_shipper_link(self, name, *, recipient_organization):
        shipper_org = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
        )
        shipper_person = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name=name.split()[0],
            last_name="Manager",
            organization=shipper_org,
        )
        shipper = wms_models.ShipmentShipper.objects.create(
            organization=shipper_org,
            default_contact=shipper_person,
            validation_status=wms_models.ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        wms_models.ShipmentShipperRecipientLink.objects.create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            is_active=True,
        )
        return shipper

    def _create_lot(self, *, product):
        self._lot_counter += 1
        return wms_models.ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-NEEDS-{self._lot_counter}",
            quantity_on_hand=500,
            location=self.location,
        )

    def _create_shipment_item(
        self,
        *,
        recipient_contact,
        product,
        quantity,
        planned_at=None,
        delivered_at=None,
        closed_at=None,
    ):
        self._shipment_counter += 1
        shipment_status = wms_models.ShipmentStatus.PLANNED
        if delivered_at is not None:
            shipment_status = wms_models.ShipmentStatus.DELIVERED
        shipment = wms_models.Shipment.objects.create(
            reference=f"26NEEDS{self._shipment_counter:04d}",
            status=shipment_status,
            shipper_name="Expediteur Test",
            recipient_name=recipient_contact.name,
            recipient_contact_ref=recipient_contact,
            correspondent_name="Correspondant",
            destination=recipient_contact.organization.shipment_recipient_organizations.first().destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        self._carton_counter += 1
        carton = wms_models.Carton.objects.create(
            code=f"C-NEEDS-{self._carton_counter}",
            status=(
                wms_models.CartonStatus.SHIPPED
                if delivered_at is not None
                else wms_models.CartonStatus.ASSIGNED
            ),
            shipment=shipment,
        )
        wms_models.CartonItem.objects.create(
            carton=carton,
            product_lot=self._create_lot(product=product),
            quantity=quantity,
        )
        wms_models.ShipmentWorkflowProjection.objects.create(
            shipment=shipment,
            destination=shipment.destination,
            reference=shipment.reference,
            shipment_status=shipment.status,
            planned_at=planned_at,
            delivered_at=delivered_at,
            closed_at=closed_at,
            is_closed=bool(closed_at),
        )
        return shipment

    def test_build_context_materializes_only_explicit_and_category_rows(self):
        category_root = self._create_category("Supplies Root")
        category_child = self._create_category("Bandages", parent=category_root)
        category_product = self._create_product(
            "NEEDS-CAT-001",
            "Bandage Pack",
            category=category_child,
        )
        unrelated_product = self._create_product(
            "NEEDS-NONE-001",
            "Unspecified Product",
            category=category_root,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=10,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            category=category_root,
            status=wms_models.RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=6,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.MONTH,
            updated_by=self.user,
        )

        request = self.factory.get("/scan/recipient-needs/")
        payload = self._helper_module().build_scan_recipient_needs_context(request)

        rows_by_product_name = {row["product_name"]: row for row in payload["rows"]}
        self.assertEqual(
            set(rows_by_product_name),
            {self.product.name, category_product.name, unrelated_product.name},
        )
        self.assertEqual(rows_by_product_name[self.product.name]["scope"], "product")
        self.assertEqual(rows_by_product_name[category_product.name]["scope"], "category")
        self.assertEqual(rows_by_product_name[unrelated_product.name]["scope"], "category")
        self.assertEqual(rows_by_product_name[self.product.name]["period_label"], "Semaine")
        self.assertEqual(rows_by_product_name[category_product.name]["period_label"], "Mois")
        self.assertNotIn("unspecified", {row["status"] for row in payload["rows"]})

    def test_build_context_applies_destination_recipient_and_category_filters_and_shipper_labels(
        self,
    ):
        target_root = self._create_category("Target Root")
        target_child = self._create_category("Target Child", parent=target_root)
        other_root = self._create_category("Other Root")
        target_product = self._create_product(
            "NEEDS-FILTER-001",
            "Filter Target",
            category=target_child,
        )
        other_product = self._create_product(
            "NEEDS-FILTER-002",
            "Filter Other",
            category=other_root,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=target_product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.other_recipient_organization,
            product=other_product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        self._create_shipper_link(
            "Zulu Shipper", recipient_organization=self.recipient_organization
        )
        self._create_shipper_link(
            "Alpha Shipper", recipient_organization=self.recipient_organization
        )

        request = self.factory.get(
            "/scan/recipient-needs/",
            {
                "destination": str(self.destination.id),
                "recipient": str(self.recipient_organization.id),
                "category": str(target_root.id),
            },
        )
        payload = self._helper_module().build_scan_recipient_needs_context(request)

        self.assertEqual(len(payload["rows"]), 1)
        row = payload["rows"][0]
        self.assertEqual(row["recipient_organization_id"], self.recipient_organization.id)
        self.assertEqual(row["destination_id"], self.destination.id)
        self.assertEqual(row["product_name"], target_product.name)
        self.assertEqual(row["shipper_labels"], ["Alpha Shipper", "Zulu Shipper"])
        self.assertEqual(payload["destination_id"], str(self.destination.id))
        self.assertEqual(payload["recipient_id"], str(self.recipient_organization.id))
        self.assertEqual(payload["category_id"], str(target_root.id))

    def test_build_context_exposes_stock_availability_and_prepare_metadata(self):
        product = self._create_product(
            "NEEDS-STOCK-001",
            "Produit Stockable",
            category=self._create_category("Stockable"),
        )
        shipper = self._create_shipper_link(
            "Single Shipper", recipient_organization=self.recipient_organization
        )
        link = wms_models.ShipmentShipperRecipientLink.objects.get(
            shipper=shipper,
            recipient_organization=self.recipient_organization,
        )
        wms_models.ShipmentAuthorizedRecipientContact.objects.create(
            link=link,
            recipient_contact=self.recipient_contact_link,
            is_default=True,
            is_active=True,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=60,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        wms_models.ProductLot.objects.create(
            product=product,
            lot_code="LOT-STOCK-READY",
            quantity_on_hand=50,
            quantity_reserved=10,
            status=wms_models.ProductLotStatus.AVAILABLE,
            location=self.location,
        )

        request = self.factory.get("/scan/recipient-needs/")
        payload = self._helper_module().build_scan_recipient_needs_context(request)

        row = next(row for row in payload["rows"] if row["product_id"] == product.id)
        self.assertEqual(row["stock_available_quantity"], 40)
        self.assertEqual(row["stock_availability_label"], "40/60")
        self.assertEqual(row["stock_availability_tone"], "warning")
        self.assertTrue(row["can_prepare"])
        self.assertEqual(row["prepare_quantity"], 40)
        self.assertEqual(row["prepare_shipper_contact_id"], shipper.default_contact_id)
        self.assertEqual(row["prepare_recipient_contact_id"], self.recipient_contact.id)

    def test_build_context_classifies_priorities_and_exposes_tooltips(self):
        critical_product = self._create_product(
            "NEEDS-PRI-001",
            "Critical Product",
            category=self.category_l3,
        )
        high_product = self._create_product(
            "NEEDS-PRI-002",
            "High Product",
            category=self.category_l3,
        )
        normal_product = self._create_product(
            "NEEDS-PRI-003",
            "Normal Product",
            category=self.category_l3,
        )
        covered_product = self._create_product(
            "NEEDS-PRI-004",
            "Covered Product",
            category=self.category_l3,
        )
        refused_product = self._create_product(
            "NEEDS-PRI-005",
            "Refused Product",
            category=self.category_l3,
        )
        for product, status, quantity, period in (
            (
                critical_product,
                wms_models.RecipientProductPreferenceStatus.REQUESTED,
                10,
                wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            ),
            (
                high_product,
                wms_models.RecipientProductPreferenceStatus.REQUESTED,
                8,
                wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            ),
            (
                normal_product,
                wms_models.RecipientProductPreferenceStatus.REQUESTED,
                10,
                wms_models.RecipientProductPreferencePeriodUnit.MONTH,
            ),
            (
                covered_product,
                wms_models.RecipientProductPreferenceStatus.REQUESTED,
                5,
                wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            ),
        ):
            wms_models.RecipientProductPreference.objects.create(
                recipient_organization=self.recipient_organization,
                product=product,
                status=status,
                quantity_target=quantity,
                period_unit=period,
                updated_by=self.user,
            )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=refused_product,
            status=wms_models.RecipientProductPreferenceStatus.REFUSED,
            updated_by=self.user,
        )

        as_of = self._aware(2026, 4, 10, 12)
        self._create_shipment_item(
            recipient_contact=self.recipient_contact,
            product=critical_product,
            quantity=2,
            planned_at=as_of - timedelta(hours=50),
        )
        self._create_shipment_item(
            recipient_contact=self.recipient_contact,
            product=normal_product,
            quantity=3,
            planned_at=as_of - timedelta(hours=6),
        )
        self._create_shipment_item(
            recipient_contact=self.recipient_contact,
            product=covered_product,
            quantity=5,
            planned_at=as_of - timedelta(hours=30),
            delivered_at=as_of - timedelta(hours=2),
        )

        request = self.factory.get("/scan/recipient-needs/")
        with patch(
            "wms.application.scan.recipient_needs_queries.get_runtime_config",
            return_value=SimpleNamespace(tracking_alert_hours=24),
        ):
            payload = self._helper_module().build_scan_recipient_needs_context(
                request,
                as_of=as_of,
            )

        rows_by_product_name = {row["product_name"]: row for row in payload["rows"]}
        self.assertEqual(rows_by_product_name["Critical Product"]["priority"], "critical")
        self.assertEqual(rows_by_product_name["High Product"]["priority"], "high")
        self.assertEqual(rows_by_product_name["Normal Product"]["priority"], "normal")
        self.assertEqual(rows_by_product_name["Covered Product"]["priority"], "covered")
        self.assertEqual(rows_by_product_name["Refused Product"]["priority"], "out_of_scope")
        self.assertIn("24h", rows_by_product_name["Critical Product"]["priority_help"])
        self.assertIn(
            "aucun pipeline",
            rows_by_product_name["High Product"]["priority_help"].lower(),
        )
        self.assertIn(
            "reste a servir 0",
            rows_by_product_name["Covered Product"]["priority_help"].lower(),
        )

    def test_build_context_filters_by_need_status_and_priority(self):
        high_product = self._create_product(
            "NEEDS-FLT-PRI-001",
            "High Filter Product",
            category=self.category_l3,
        )
        covered_product = self._create_product(
            "NEEDS-FLT-PRI-002",
            "Covered Filter Product",
            category=self.category_l3,
        )
        refused_product = self._create_product(
            "NEEDS-FLT-PRI-003",
            "Refused Filter Product",
            category=self.category_l3,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=high_product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=8,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=covered_product,
            status=wms_models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=5,
            period_unit=wms_models.RecipientProductPreferencePeriodUnit.WEEK,
            updated_by=self.user,
        )
        wms_models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=refused_product,
            status=wms_models.RecipientProductPreferenceStatus.REFUSED,
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 10, 12)
        self._create_shipment_item(
            recipient_contact=self.recipient_contact,
            product=covered_product,
            quantity=5,
            planned_at=as_of - timedelta(hours=8),
            delivered_at=as_of - timedelta(hours=1),
        )

        high_only_request = self.factory.get(
            "/scan/recipient-needs/",
            {
                "need_status": "to_serve",
                "priority": "high",
            },
        )
        refused_request = self.factory.get(
            "/scan/recipient-needs/",
            {
                "need_status": "refused",
            },
        )

        helper = self._helper_module()
        high_only_payload = helper.build_scan_recipient_needs_context(
            high_only_request, as_of=as_of
        )
        refused_payload = helper.build_scan_recipient_needs_context(refused_request, as_of=as_of)

        self.assertEqual(
            [row["product_name"] for row in high_only_payload["rows"]],
            ["High Filter Product"],
        )
        self.assertEqual(
            [row["product_name"] for row in refused_payload["rows"]],
            ["Refused Filter Product"],
        )
