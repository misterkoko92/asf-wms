from datetime import datetime
from unittest.mock import patch

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

    def test_private_period_helpers_cover_none_naive_december_and_unknown_units(self):
        helper = self._helper_module()

        self.assertTrue(timezone.is_aware(helper._normalize_as_of(None)))
        normalized_naive = helper._normalize_as_of(datetime(2026, 12, 15, 8, 30))
        self.assertTrue(timezone.is_aware(normalized_naive))

        period_start, period_end = helper._resolve_period_window(
            as_of=self._aware(2026, 12, 15, 10),
            period_unit="month",
        )
        unknown_start, unknown_end = helper._resolve_period_window(
            as_of=self._aware(2026, 4, 15, 10),
            period_unit="quarter",
        )

        self.assertEqual(period_start, self._aware(2026, 12, 1, 0))
        self.assertEqual(period_end, self._aware(2027, 1, 1, 0))
        self.assertIsNone(unknown_start)
        self.assertIsNone(unknown_end)

    def test_iter_recipient_rows_handles_empty_contact_ids_and_missing_projection(self):
        helper = self._helper_module()
        lot = self._create_lot(product=self.product)

        with patch.object(helper, "_recipient_contact_ids", return_value=set()):
            rows = list(
                helper._iter_recipient_shipment_product_rows(
                    recipient_organization=self.recipient_organization,
                    product=self.product,
                )
            )

        self.assertEqual(rows, [])

        shipment = wms_models.Shipment.objects.create(
            reference="26COVNOPROJ",
            shipper_name="Expediteur",
            recipient_name=self.recipient_contact.name,
            recipient_contact_ref=self.recipient_contact,
            correspondent_name="Correspondant",
            destination=self.destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        carton = wms_models.Carton.objects.create(
            code="C-COV-NOPROJ",
            status=wms_models.CartonStatus.ASSIGNED,
            shipment=shipment,
        )
        wms_models.CartonItem.objects.create(
            carton=carton,
            product_lot=lot,
            quantity=4,
        )

        rows = list(
            helper._iter_recipient_shipment_product_rows(
                recipient_organization=self.recipient_organization,
                product=self.product,
            )
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 4)
        self.assertEqual(rows[0][1], shipment)
        self.assertIsNone(rows[0][2])


class RecipientParcelCompatibilityTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.recipient_contact = Contact.objects.create(
            contact_type=ContactType.PERSON,
            first_name="Bob",
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

    def _create_product(self, *, sku, name):
        return wms_models.Product.objects.create(
            sku=sku,
            name=name,
            brand="ASF",
            qr_code_image=f"qr_codes/{sku}.png",
        )

    def _create_lot(self, *, product=None):
        self._lot_counter += 1
        target_product = product or self.product
        return wms_models.ProductLot.objects.create(
            product=target_product,
            lot_code=f"LOT-COMP-{self._lot_counter}",
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
            reference=f"26COMP{self._shipment_counter:04d}",
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
            code=f"C-COMP-SHIP-{self._carton_counter}",
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

    def _create_carton(self, *, product, quantity):
        self._carton_counter += 1
        carton = wms_models.Carton.objects.create(
            code=f"C-COMP-{self._carton_counter}",
            status=wms_models.CartonStatus.PACKED,
        )
        wms_models.CartonItem.objects.create(
            carton=carton,
            product_lot=self._create_lot(product=product),
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

    def test_explicit_products_without_active_need_are_marked_a_eviter(self):
        helper = self._helper_module()
        allowed_product = self._create_product(
            sku="PREF-COMP-ALLOWED-EXCESS",
            name="Produit Autorise Excess",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=2,
            period_unit="week",
            updated_by=self.user,
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=allowed_product,
            status="allowed",
            quantity_target=1,
            period_unit="week",
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 8, 12)
        self._create_shipment_item(
            product=self.product,
            quantity=2,
            delivered_at=self._aware(2026, 4, 7, 9),
        )
        self._create_shipment_item(
            product=allowed_product,
            quantity=1,
            delivered_at=self._aware(2026, 4, 7, 10),
        )
        requested_carton = self._create_carton(product=self.product, quantity=3)
        allowed_carton = self._create_carton(product=allowed_product, quantity=2)

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

        self.assertEqual(requested.bucket, "a_eviter")
        self.assertEqual(allowed.bucket, "a_eviter")
        self.assertIn("sans besoin actif", requested.explanation)
        self.assertIn("sans besoin actif", allowed.explanation)

    def test_missing_coverages_fall_back_to_unspecified_compatible_bucket(self):
        helper = self._helper_module()
        carton = self._create_carton(product=self.product, quantity=3)

        with (
            patch.object(
                helper,
                "list_recipient_refusal_conflicts_for_carton",
                return_value=[],
            ),
            patch.object(
                helper,
                "list_recipient_product_coverages",
                return_value=[],
            ),
        ):
            compatibility = helper.score_recipient_carton_compatibility(
                recipient_organization=self.recipient_organization,
                carton=carton,
                as_of=self._aware(2026, 4, 8, 12),
            )

        self.assertEqual(compatibility.bucket, "compatibles")
        self.assertEqual(compatibility.score, 3)
        self.assertIn("sans besoin exprime", compatibility.explanation)

    def test_bulk_compatibilities_cover_history_and_bucket_branches(self):
        helper = self._helper_module()
        allowed_fresh_product = self._create_product(
            sku="PREF-COMP-BULK-ALLOWED",
            name="Produit autorise bulk",
        )
        allowed_fresh_product.category = self.category_l2
        allowed_fresh_product.save(update_fields=["category"])
        allowed_exhausted_product = self._create_product(
            sku="PREF-COMP-BULK-EXCESS",
            name="Produit autorise excess bulk",
        )
        allowed_exhausted_product.category = self.category_l2
        allowed_exhausted_product.save(update_fields=["category"])
        unspecified_product = self._create_product(
            sku="PREF-COMP-BULK-OPEN",
            name="Produit libre bulk",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=2,
            period_unit="week",
            updated_by=self.user,
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            category=self.category_l2,
            status="allowed",
            quantity_target=3,
            period_unit="week",
            updated_by=self.user,
        )
        as_of = self._aware(2026, 4, 8, 12)
        self._create_shipment_item(
            product=self.product,
            quantity=2,
            delivered_at=self._aware(2026, 4, 7, 9),
        )
        self._create_shipment_item(
            product=allowed_exhausted_product,
            quantity=2,
            delivered_at=self._aware(2026, 4, 7, 10),
        )
        self._create_shipment_item(product=allowed_exhausted_product, quantity=1)
        requested_excess_carton = self._create_carton(product=self.product, quantity=1)
        allowed_fresh_carton = self._create_carton(product=allowed_fresh_product, quantity=2)
        allowed_excess_carton = self._create_carton(product=allowed_exhausted_product, quantity=2)
        unspecified_carton = self._create_carton(product=unspecified_product, quantity=3)

        result = helper.score_recipient_carton_compatibilities(
            recipient_organizations=[self.recipient_organization],
            cartons=[
                requested_excess_carton,
                allowed_fresh_carton,
                allowed_excess_carton,
                unspecified_carton,
            ],
            as_of=as_of,
        )

        requested_excess = result[requested_excess_carton.id][self.recipient_organization.id]
        allowed_fresh = result[allowed_fresh_carton.id][self.recipient_organization.id]
        allowed_excess = result[allowed_excess_carton.id][self.recipient_organization.id]
        unspecified = result[unspecified_carton.id][self.recipient_organization.id]
        self.assertEqual(requested_excess.bucket, "a_eviter")
        self.assertEqual(requested_excess.score, -20)
        self.assertEqual(allowed_fresh.bucket, "compatibles")
        self.assertEqual(allowed_fresh.score, 60)
        self.assertEqual(allowed_excess.bucket, "a_eviter")
        self.assertEqual(allowed_excess.score, -10)
        self.assertEqual(unspecified.bucket, "compatibles")
        self.assertEqual(unspecified.score, 3)
