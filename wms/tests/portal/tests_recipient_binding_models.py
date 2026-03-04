from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)


class RecipientBindingModelTests(TestCase):
    def _create_organization(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_organization(f"Correspondent {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_shipper_scope_requires_all_destinations_xor_destination(self):
        shipper = self._create_organization("Shipper Scope")
        assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        destination = self._create_destination("AAA")

        with self.assertRaises(ValidationError) as both_set:
            ShipperScope(
                role_assignment=assignment,
                all_destinations=True,
                destination=destination,
            ).full_clean()
        self.assertIn("__all__", both_set.exception.message_dict)

        with self.assertRaises(ValidationError) as neither_set:
            ShipperScope(
                role_assignment=assignment,
                all_destinations=False,
                destination=None,
            ).full_clean()
        self.assertIn("__all__", neither_set.exception.message_dict)

        ShipperScope(
            role_assignment=assignment,
            all_destinations=True,
            destination=None,
        ).full_clean()

    def test_recipient_binding_requires_destination(self):
        shipper = self._create_organization("Shipper A")
        recipient = self._create_organization("Recipient A")

        with self.assertRaises(ValidationError) as exc:
            RecipientBinding(
                shipper_org=shipper,
                recipient_org=recipient,
                destination=None,
            ).full_clean()
        self.assertIn("destination", exc.exception.message_dict)

    def test_recipient_binding_requires_valid_to_after_valid_from(self):
        shipper = self._create_organization("Shipper B")
        recipient = self._create_organization("Recipient B")
        destination = self._create_destination("BBB")
        valid_from = timezone.now()

        with self.assertRaises(ValidationError) as exc:
            RecipientBinding(
                shipper_org=shipper,
                recipient_org=recipient,
                destination=destination,
                valid_from=valid_from,
                valid_to=valid_from - timedelta(minutes=1),
            ).full_clean()
        self.assertIn("valid_to", exc.exception.message_dict)

    def test_recipient_binding_supports_versioned_history(self):
        shipper = self._create_organization("Shipper C")
        recipient = self._create_organization("Recipient C")
        destination = self._create_destination("CCC")
        first_from = timezone.now() - timedelta(days=2)
        second_from = timezone.now() - timedelta(days=1)

        first = RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=False,
            valid_from=first_from,
            valid_to=second_from,
        )
        second = RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=True,
            valid_from=second_from,
        )

        self.assertLess(first.valid_from, second.valid_from)
        self.assertIsNotNone(first.valid_to)
