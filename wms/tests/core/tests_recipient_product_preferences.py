from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    Product,
    ProductCategory,
    ProductKitItem,
    RecipientProductPreference,
    RecipientProductPreferencePeriodUnit,
    RecipientProductPreferenceStatus,
    ShipmentRecipientOrganization,
)
from wms.recipient_product_preferences import (
    resolve_effective_recipient_product_preference,
)


class RecipientProductPreferenceModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prefs@example.com",
            email="prefs@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.recipient_org = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Corinne",
            last_name="Dest",
            email="corinne.dest@example.com",
            organization=self.recipient_org,
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
            organization=self.recipient_org,
            destination=self.destination,
            validation_status="validated",
        )
        self.category_l2 = ProductCategory.objects.create(name="Kits")
        self.category_l3 = ProductCategory.objects.create(
            name="Obstetrique",
            parent=self.category_l2,
        )
        self.product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category_l3,
        )

    def test_requested_and_allowed_can_target_product_or_category(self):
        product_pref = RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.product,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=4,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )
        category_pref = RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            category=self.category_l2,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=12,
            period_unit=RecipientProductPreferencePeriodUnit.MONTH,
            created_by=self.user,
        )

        self.assertEqual(product_pref.product, self.product)
        self.assertEqual(category_pref.category, self.category_l2)

    def test_category_level_refused_is_rejected(self):
        preference = RecipientProductPreference(
            recipient_organization=self.recipient,
            category=self.category_l2,
            status=RecipientProductPreferenceStatus.REFUSED,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            preference.full_clean()


class RecipientProductPreferenceResolutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="prefs-resolution@example.com",
            email="prefs-resolution@example.com",
            password="pass1234",  # pragma: allowlist secret
        )
        self.recipient_org = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.correspondent = Contact.objects.create(
            first_name="Claire",
            last_name="Dest",
            email="claire.dest@example.com",
            organization=self.recipient_org,
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Douala",
            iata_code="DLA",
            country="CM",
            correspondent_contact=self.correspondent,
        )
        self.recipient = ShipmentRecipientOrganization.objects.create(
            organization=self.recipient_org,
            destination=self.destination,
            validation_status="validated",
        )
        self.category_l2 = ProductCategory.objects.create(name="Kits")
        self.category_l3 = ProductCategory.objects.create(
            name="Obstetrique",
            parent=self.category_l2,
        )
        self.product = Product.objects.create(
            name="Kit Accouchement",
            category=self.category_l3,
        )
        self.other_product = Product.objects.create(
            name="Kit Accouchement 2",
            category=self.category_l3,
        )
        self.component = Product.objects.create(
            name="Gants steriles",
            category=self.category_l2,
        )
        self.kit = Product.objects.create(
            name="Kit Maternite",
            category=self.category_l3,
        )
        ProductKitItem.objects.create(kit=self.kit, component=self.component, quantity=2)

    def test_exact_product_preference_wins_over_category_preference(self):
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            category=self.category_l3,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=8,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.product,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=2,
            period_unit=RecipientProductPreferencePeriodUnit.MONTH,
            created_by=self.user,
        )

        resolved = resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient,
            product=self.product,
        )

        self.assertEqual(resolved.status, RecipientProductPreferenceStatus.ALLOWED)
        self.assertEqual(resolved.quantity_target, 2)
        self.assertEqual(resolved.period_unit, RecipientProductPreferencePeriodUnit.MONTH)
        self.assertEqual(resolved.scope, "product")

    def test_more_specific_category_wins_over_broader_category(self):
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            category=self.category_l2,
            status=RecipientProductPreferenceStatus.ALLOWED,
            quantity_target=12,
            period_unit=RecipientProductPreferencePeriodUnit.MONTH,
            created_by=self.user,
        )
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            category=self.category_l3,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=6,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )

        resolved = resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient,
            product=self.other_product,
        )

        self.assertEqual(resolved.status, RecipientProductPreferenceStatus.REQUESTED)
        self.assertEqual(resolved.quantity_target, 6)
        self.assertEqual(resolved.period_unit, RecipientProductPreferencePeriodUnit.WEEK)
        self.assertEqual(resolved.scope, "category")

    def test_missing_preference_resolves_to_unspecified(self):
        resolved = resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient,
            product=self.product,
        )

        self.assertEqual(resolved.status, "unspecified")
        self.assertIsNone(resolved.quantity_target)
        self.assertIsNone(resolved.period_unit)
        self.assertEqual(resolved.scope, "unspecified")

    def test_kit_resolution_uses_kit_product_itself_not_components(self):
        RecipientProductPreference.objects.create(
            recipient_organization=self.recipient,
            product=self.component,
            status=RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=10,
            period_unit=RecipientProductPreferencePeriodUnit.WEEK,
            created_by=self.user,
        )

        resolved = resolve_effective_recipient_product_preference(
            recipient_organization=self.recipient,
            product=self.kit,
        )

        self.assertEqual(resolved.status, "unspecified")
        self.assertEqual(resolved.scope, "unspecified")
