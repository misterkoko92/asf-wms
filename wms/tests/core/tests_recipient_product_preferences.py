from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms import models as wms_models


class RecipientProductPreferenceTestDataMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="recipient-preferences-user",
            password="pass1234",  # pragma: allowlist secret
        )
        self.recipient_org_contact = Contact.objects.create(
            name="Hopital Recipient",
            contact_type=ContactType.ORGANIZATION,
        )
        self.correspondent_contact = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
        )
        self.destination = wms_models.Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent_contact,
            is_active=True,
        )
        self.recipient_organization = wms_models.ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_org_contact,
            destination=self.destination,
            is_active=True,
        )
        self.product = wms_models.Product.objects.create(
            sku="PREF-001",
            name="Gants Steriles",
            brand="ASF",
            qr_code_image="qr_codes/pref-001.png",
        )
        self.shipment = wms_models.Shipment.objects.create(
            reference="260001",
            shipper_name="Expediteur",
            recipient_name="Destinataire",
            correspondent_name="Correspondant",
            destination=self.destination,
            destination_address="10 Rue Test",
            destination_country="Mali",
        )
        self.warehouse = wms_models.Warehouse.objects.create(name="Warehouse Prefs")
        self.location = wms_models.Location.objects.create(
            warehouse=self.warehouse,
            zone="A",
            aisle="01",
            shelf="001",
        )
        self.carton = wms_models.Carton.objects.create(
            code="C-PREF-1",
            status=wms_models.CartonStatus.PACKED,
        )

    def _preference_model(self):
        model = getattr(wms_models, "RecipientProductPreference", None)
        self.assertIsNotNone(model)
        return model

    def _override_model(self):
        model = getattr(wms_models, "ShipmentPreferenceOverride", None)
        self.assertIsNotNone(model)
        return model


class RecipientProductPreferenceModelTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def test_preference_models_are_exported_from_wms_models(self):
        self.assertIsNotNone(getattr(wms_models, "RecipientProductPreference", None))
        self.assertIsNotNone(getattr(wms_models, "ShipmentPreferenceOverride", None))

    def test_requested_preference_requires_quantity_and_period(self):
        preference_model = self._preference_model()
        preference = preference_model(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError) as exc:
            preference.full_clean()

        self.assertIn("quantity_target", exc.exception.message_dict)
        self.assertIn("period_unit", exc.exception.message_dict)

    def test_allowed_preference_requires_quantity_and_period(self):
        preference_model = self._preference_model()
        preference = preference_model(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="allowed",
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError) as exc:
            preference.full_clean()

        self.assertIn("quantity_target", exc.exception.message_dict)
        self.assertIn("period_unit", exc.exception.message_dict)

    def test_refused_preference_rejects_quantity_fields(self):
        preference_model = self._preference_model()
        preference = preference_model(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            quantity_target=50,
            period_unit="week",
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError) as exc:
            preference.full_clean()

        self.assertIn("quantity_target", exc.exception.message_dict)
        self.assertIn("period_unit", exc.exception.message_dict)

    def test_preference_is_unique_per_recipient_organization_and_product(self):
        preference_model = self._preference_model()
        preference_model.objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=50,
            period_unit="week",
            updated_by=self.user,
        )

        with self.assertRaises(ValidationError) as exc:
            preference_model.objects.create(
                recipient_organization=self.recipient_organization,
                product=self.product,
                status="allowed",
                quantity_target=20,
                period_unit="month",
                updated_by=self.user,
            )

        self.assertIn("__all__", exc.exception.message_dict)

    def test_override_can_be_created_without_mutating_canonical_preference(self):
        preference_model = self._preference_model()
        override_model = self._override_model()
        preference = preference_model.objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )

        override = override_model.objects.create(
            shipment=self.shipment,
            carton=self.carton,
            recipient_organization=self.recipient_organization,
            product=self.product,
            preference_status_snapshot="refused",
            action="override_refusal",
            created_by=self.user,
        )

        preference.refresh_from_db()

        self.assertEqual(preference.status, "refused")
        self.assertEqual(override.preference_status_snapshot, "refused")

    def test_preference_string_representation_and_inactive_recipient_validation(self):
        preference_model = self._preference_model()
        preference = preference_model(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=8,
            period_unit="week",
            updated_by=self.user,
        )

        self.assertIn("requested", str(preference))
        self.assertIn(self.product.name, str(preference))

        self.recipient_organization.is_active = False
        self.recipient_organization.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError) as exc:
            preference.full_clean()

        self.assertIn("recipient_organization", exc.exception.message_dict)

    def test_override_string_representation_and_inactive_recipient_validation(self):
        override_model = self._override_model()
        override = override_model(
            shipment=self.shipment,
            carton=self.carton,
            recipient_organization=self.recipient_organization,
            product=self.product,
            preference_status_snapshot="refused",
            action="override_refusal",
            created_by=self.user,
        )

        self.assertIn("override_refusal", str(override))
        self.assertIn(self.product.name, str(override))

        self.recipient_organization.is_active = False
        self.recipient_organization.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError) as exc:
            override.full_clean()

        self.assertIn("recipient_organization", exc.exception.message_dict)


class RecipientProductPreferenceResolutionTests(RecipientProductPreferenceTestDataMixin, TestCase):
    def _helper_module(self):
        from wms import recipient_product_preferences

        return recipient_product_preferences

    def test_missing_row_resolves_to_implicit_unspecified(self):
        helper = self._helper_module()

        resolved = helper.resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient_organization,
            product=self.product,
        )

        self.assertEqual(resolved.status, "unspecified")
        self.assertFalse(resolved.is_explicit)
        self.assertIsNone(resolved.preference)
        self.assertIsNone(resolved.quantity_target)
        self.assertIsNone(resolved.period_unit)

    def test_explicit_rows_resolve_to_stored_status(self):
        preference = self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="requested",
            quantity_target=10,
            period_unit="week",
            updated_by=self.user,
        )
        helper = self._helper_module()

        resolved = helper.resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient_organization,
            product=self.product,
        )

        self.assertEqual(resolved.status, "requested")
        self.assertTrue(resolved.is_explicit)
        self.assertEqual(resolved.preference.pk, preference.pk)

    def test_resolution_exposes_targets_only_for_requested_and_allowed(self):
        second_product = wms_models.Product.objects.create(
            sku="PREF-002",
            name="Compresses",
            brand="ASF",
            qr_code_image="qr_codes/pref-002.png",
        )
        third_product = wms_models.Product.objects.create(
            sku="PREF-003",
            name="Bandages",
            brand="ASF",
            qr_code_image="qr_codes/pref-003.png",
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
            product=second_product,
            status="allowed",
            quantity_target=25,
            period_unit="month",
            updated_by=self.user,
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=third_product,
            status="refused",
            updated_by=self.user,
        )
        helper = self._helper_module()

        requested = helper.resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient_organization,
            product=self.product,
        )
        allowed = helper.resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient_organization,
            product=second_product,
        )
        refused = helper.resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient_organization,
            product=third_product,
        )

        self.assertEqual((requested.quantity_target, requested.period_unit), (10, "week"))
        self.assertEqual((allowed.quantity_target, allowed.period_unit), (25, "month"))
        self.assertIsNone(refused.quantity_target)
        self.assertIsNone(refused.period_unit)

    def test_list_carton_product_quantities_groups_same_product(self):
        helper = self._helper_module()
        second_lot = wms_models.ProductLot.objects.create(
            product=self.product,
            quantity_on_hand=5,
            location=self.location,
        )
        wms_models.CartonItem.objects.create(
            carton=self.carton,
            product_lot=wms_models.ProductLot.objects.create(
                product=self.product,
                quantity_on_hand=5,
                location=self.location,
            ),
            quantity=2,
        )
        wms_models.CartonItem.objects.create(
            carton=self.carton,
            product_lot=second_lot,
            quantity=3,
        )

        rows = helper.list_carton_product_quantities(carton=self.carton)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].product.pk, self.product.pk)
        self.assertEqual(rows[0].quantity, 5)

    def test_recipient_has_explicit_refused_preferences_detects_refused_rows(self):
        helper = self._helper_module()
        self.assertFalse(
            helper.recipient_has_explicit_refused_preferences(
                recipient_organization=self.recipient_organization
            )
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )

        self.assertTrue(
            helper.recipient_has_explicit_refused_preferences(
                recipient_organization=self.recipient_organization
            )
        )

    def test_list_recipient_refusal_conflicts_for_carton_returns_explicit_refusals(self):
        helper = self._helper_module()
        second_product = wms_models.Product.objects.create(
            sku="PREF-004",
            name="Pansements",
            brand="ASF",
            qr_code_image="qr_codes/pref-004.png",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=second_product,
            status="allowed",
            quantity_target=4,
            period_unit="week",
            updated_by=self.user,
        )
        wms_models.CartonItem.objects.create(
            carton=self.carton,
            product_lot=wms_models.ProductLot.objects.create(
                product=self.product,
                quantity_on_hand=5,
                location=self.location,
            ),
            quantity=2,
        )
        wms_models.CartonItem.objects.create(
            carton=self.carton,
            product_lot=wms_models.ProductLot.objects.create(
                product=second_product,
                quantity_on_hand=5,
                location=self.location,
            ),
            quantity=1,
        )

        conflicts = helper.list_recipient_refusal_conflicts_for_carton(
            recipient_organization=self.recipient_organization,
            carton=self.carton,
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].product.pk, self.product.pk)
        self.assertEqual(conflicts[0].quantity, 2)
        self.assertEqual(conflicts[0].preference.status, "refused")

    def test_list_recipient_refusal_conflicts_for_products_ignores_unspecified(self):
        helper = self._helper_module()
        second_product = wms_models.Product.objects.create(
            sku="PREF-005",
            name="Masques",
            brand="ASF",
            qr_code_image="qr_codes/pref-005.png",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )

        conflicts = helper.list_recipient_refusal_conflicts_for_products(
            recipient_organization=self.recipient_organization,
            products=[self.product, second_product],
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].product.pk, self.product.pk)
        self.assertIsNone(conflicts[0].quantity)

    def test_list_effective_preferences_includes_missing_products_as_unspecified(self):
        second_product = wms_models.Product.objects.create(
            sku="PREF-004",
            name="Masques",
            brand="ASF",
            qr_code_image="qr_codes/pref-004.png",
        )
        self._preference_model().objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status="refused",
            updated_by=self.user,
        )
        helper = self._helper_module()

        resolved = helper.list_effective_recipient_product_preferences(
            recipient_organization=self.recipient_organization,
            products=[self.product, second_product],
        )

        self.assertEqual(
            [item.product.pk for item in resolved], [self.product.pk, second_product.pk]
        )
        self.assertEqual([item.status for item in resolved], ["refused", "unspecified"])

    def test_list_effective_preferences_returns_empty_for_empty_products(self):
        helper = self._helper_module()

        resolved = helper.list_effective_recipient_product_preferences(
            recipient_organization=self.recipient_organization,
            products=[],
        )

        self.assertEqual(resolved, [])

    def test_list_carton_product_quantities_returns_empty_without_related_manager(self):
        helper = self._helper_module()

        rows = helper.list_carton_product_quantities(carton=object())

        self.assertEqual(rows, [])

    def test_refusal_conflict_helpers_return_empty_for_empty_inputs(self):
        helper = self._helper_module()

        product_conflicts = helper.list_recipient_refusal_conflicts_for_products(
            recipient_organization=self.recipient_organization,
            products=[],
        )
        carton_conflicts = helper.list_recipient_refusal_conflicts_for_carton(
            recipient_organization=self.recipient_organization,
            carton=object(),
        )

        self.assertEqual(product_conflicts, [])
        self.assertEqual(carton_conflicts, [])
