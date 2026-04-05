from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms import models as wms_models
from wms.tests.core.tests_recipient_product_preferences import (
    RecipientProductPreferenceTestDataMixin,
)


class RecipientProductPreferenceCoverageTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
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
        self._shipment_counter = 0
        self._carton_counter = 0
        self._lot_counter = 0

    def _helper_module(self):
        from wms import recipient_product_preferences

        return recipient_product_preferences

    def _aware(self, year, month, day, hour=12, minute=0):
        return timezone.make_aware(
            datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )

    def _create_lot(self, *, product=None):
        self._lot_counter += 1
        target_product = product or self.product
        return wms_models.ProductLot.objects.create(
            product=target_product,
            lot_code=f"LOT-COV-{self._lot_counter}",
            quantity_on_hand=200,
            location=self.location,
        )

    def _create_shipment_item(
        self,
        *,
        product=None,
        quantity=1,
        delivered_at=None,
        closed_at=None,
        recipient_contact=None,
    ):
        self._shipment_counter += 1
        target_contact = recipient_contact or self.recipient_contact
        shipment = wms_models.Shipment.objects.create(
            reference=f"26COV{self._shipment_counter:04d}",
            shipper_name="Expediteur",
            recipient_name=target_contact.name,
            recipient_contact_ref=target_contact,
            correspondent_name="Correspondant",
            destination=self.destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        self._carton_counter += 1
        carton = wms_models.Carton.objects.create(
            code=f"C-COV-{self._carton_counter}",
            status=(
                wms_models.CartonStatus.SHIPPED
                if delivered_at
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
            destination=self.destination,
            reference=shipment.reference,
            delivered_at=delivered_at,
            closed_at=closed_at,
            is_closed=bool(closed_at),
        )
        return shipment

    def test_weekly_coverage_uses_monday_sunday_boundaries(self):
        helper = self._helper_module()
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=10,
            period_unit="week",
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 8, 14)
        self._create_shipment_item(
            quantity=3,
            delivered_at=self._aware(2026, 4, 6, 9),
        )
        self._create_shipment_item(
            quantity=1,
            delivered_at=self._aware(2026, 4, 12, 21),
        )
        self._create_shipment_item(
            quantity=2,
            delivered_at=self._aware(2026, 4, 5, 23),
        )

        coverage = helper.resolve_recipient_product_coverage(
            recipient_organization=self.recipient_organization,
            product=self.product,
            as_of=as_of,
        )

        self.assertEqual(coverage.period_start, self._aware(2026, 4, 6, 0))
        self.assertEqual(coverage.period_end, self._aware(2026, 4, 13, 0))
        self.assertEqual(coverage.delivered_quantity, 4)

    def test_monthly_coverage_uses_calendar_month_boundaries(self):
        helper = self._helper_module()
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="allowed",
            quantity_target=20,
            period_unit="month",
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 15, 10)
        self._create_shipment_item(
            quantity=4,
            delivered_at=self._aware(2026, 4, 1, 0, 30),
        )
        self._create_shipment_item(
            quantity=7,
            delivered_at=self._aware(2026, 3, 31, 23, 30),
        )

        coverage = helper.resolve_recipient_product_coverage(
            recipient_organization=self.recipient_organization,
            product=self.product,
            as_of=as_of,
        )

        self.assertEqual(coverage.period_start, self._aware(2026, 4, 1, 0))
        self.assertEqual(coverage.period_end, self._aware(2026, 5, 1, 0))
        self.assertEqual(coverage.delivered_quantity, 4)

    def test_remaining_need_subtracts_delivered_and_pipeline_quantities(self):
        helper = self._helper_module()
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=10,
            period_unit="week",
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 8, 16)
        self._create_shipment_item(
            quantity=3,
            delivered_at=self._aware(2026, 4, 7, 9),
        )
        self._create_shipment_item(quantity=2)

        coverage = helper.resolve_recipient_product_coverage(
            recipient_organization=self.recipient_organization,
            product=self.product,
            as_of=as_of,
        )

        self.assertEqual(coverage.target_quantity, 10)
        self.assertEqual(coverage.delivered_quantity, 3)
        self.assertEqual(coverage.pipeline_quantity, 2)
        self.assertEqual(coverage.remaining_need, 5)

    def test_unspecified_and_refused_preferences_do_not_compute_quantity_coverage(self):
        helper = self._helper_module()
        refused_product = wms_models.Product.objects.create(
            sku="PREF-COV-REFUSED",
            name="Produit Refuse",
            brand="ASF",
            qr_code_image="qr_codes/pref-cov-refused.png",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=refused_product,
            status="refused",
            updated_by=self.user,
        )

        unspecified = helper.resolve_recipient_product_coverage(
            recipient_organization=self.recipient_organization,
            product=self.product,
            as_of=self._aware(2026, 4, 8, 12),
        )
        refused = helper.resolve_recipient_product_coverage(
            recipient_organization=self.recipient_organization,
            product=refused_product,
            as_of=self._aware(2026, 4, 8, 12),
        )

        self.assertEqual(unspecified.status, "unspecified")
        self.assertIsNone(unspecified.target_quantity)
        self.assertIsNone(unspecified.delivered_quantity)
        self.assertIsNone(unspecified.pipeline_quantity)
        self.assertIsNone(unspecified.remaining_need)
        self.assertEqual(refused.status, "refused")
        self.assertIsNone(refused.target_quantity)
        self.assertIsNone(refused.delivered_quantity)
        self.assertIsNone(refused.pipeline_quantity)
        self.assertIsNone(refused.remaining_need)


class RecipientParcelCompatibilityTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self._carton_counter = 0
        self._lot_counter = 0

    def _helper_module(self):
        from wms import recipient_product_preferences

        return recipient_product_preferences

    def _aware(self, year, month, day, hour=12, minute=0):
        return timezone.make_aware(
            datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )

    def _create_product(self, *, sku, name):
        return wms_models.Product.objects.create(
            sku=sku,
            name=name,
            brand="ASF",
            qr_code_image=f"qr_codes/{sku}.png",
        )

    def _create_carton(self, *, product, quantity):
        self._carton_counter += 1
        self._lot_counter += 1
        carton = wms_models.Carton.objects.create(
            code=f"C-COMP-{self._carton_counter}",
            status=wms_models.CartonStatus.PACKED,
        )
        lot = wms_models.ProductLot.objects.create(
            product=product,
            lot_code=f"LOT-COMP-{self._lot_counter}",
            quantity_on_hand=200,
            location=self.location,
        )
        wms_models.CartonItem.objects.create(
            carton=carton,
            product_lot=lot,
            quantity=quantity,
        )
        return carton

    def test_parcels_with_refused_products_are_incompatibles(self):
        helper = self._helper_module()
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )
        carton = self._create_carton(product=self.product, quantity=2)

        compatibility = helper.score_recipient_carton_compatibility(
            recipient_organization=self.recipient_organization,
            carton=carton,
            as_of=self._aware(2026, 4, 8, 12),
        )

        self.assertEqual(compatibility.bucket, "incompatibles")
        self.assertLess(compatibility.score, 0)
        self.assertIn("refuse", compatibility.explanation)

    def test_requested_need_outranks_allowed_and_unspecified_parcels(self):
        helper = self._helper_module()
        allowed_product = self._create_product(
            sku="PREF-COMP-ALLOWED",
            name="Produit Autorise",
        )
        unspecified_product = self._create_product(
            sku="PREF-COMP-UNSPECIFIED",
            name="Produit Libre",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=10,
            period_unit="week",
            updated_by=self.user,
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=allowed_product,
            status="allowed",
            quantity_target=10,
            period_unit="month",
            updated_by=self.user,
        )
        requested_carton = self._create_carton(product=self.product, quantity=2)
        allowed_carton = self._create_carton(product=allowed_product, quantity=2)
        unspecified_carton = self._create_carton(product=unspecified_product, quantity=2)
        as_of = self._aware(2026, 4, 8, 12)

        requested = helper.score_recipient_carton_compatibility(
            recipient_organization=self.recipient_organization,
            carton=requested_carton,
            as_of=as_of,
        )
        allowed = helper.score_recipient_carton_compatibility(
            recipient_organization=self.recipient_organization,
            carton=allowed_carton,
            as_of=as_of,
        )
        unspecified = helper.score_recipient_carton_compatibility(
            recipient_organization=self.recipient_organization,
            carton=unspecified_carton,
            as_of=as_of,
        )

        self.assertEqual(requested.bucket, "tres_adaptes")
        self.assertEqual(allowed.bucket, "compatibles")
        self.assertEqual(unspecified.bucket, "compatibles")
        self.assertGreater(requested.score, allowed.score)
        self.assertGreater(allowed.score, unspecified.score)
