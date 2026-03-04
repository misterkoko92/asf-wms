from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.correspondent_routing import (
    build_coordination_message_for_correspondent,
    resolve_correspondent_organizations,
)
from wms.models import (
    Destination,
    DestinationCorrespondentDefault,
    DestinationCorrespondentOverride,
)


class CorrespondentRoutingTests(TestCase):
    def _create_org(self, name: str, *, email: str = "") -> Contact:
        return Contact.objects.create(
            name=name,
            email=email,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> Destination:
        fallback = self._create_org(f"Fallback {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=fallback,
            is_active=True,
        )

    def test_resolver_returns_union_default_and_overrides(self):
        destination = self._create_destination("CRT")
        shipper = self._create_org("Shipper CRT")
        recipient = self._create_org("Recipient CRT")
        default_corr = self._create_org("Default Corr CRT")
        dedicated_corr = self._create_org("Dedicated Corr CRT")

        DestinationCorrespondentDefault.objects.create(
            destination=destination,
            correspondent_org=default_corr,
            is_active=True,
        )
        DestinationCorrespondentOverride.objects.create(
            destination=destination,
            correspondent_org=dedicated_corr,
            shipper_org=shipper,
            is_active=True,
        )

        resolved = resolve_correspondent_organizations(
            destination=destination,
            shipper_org=shipper,
            recipient_org=recipient,
        )
        self.assertEqual(
            {org.id for org in resolved},
            {default_corr.id, dedicated_corr.id},
        )

    def test_resolver_deduplicates_same_correspondent(self):
        destination = self._create_destination("CRD")
        shipper = self._create_org("Shipper CRD")
        recipient = self._create_org("Recipient CRD")
        corr = self._create_org("Shared Corr CRD")

        DestinationCorrespondentDefault.objects.create(
            destination=destination,
            correspondent_org=corr,
            is_active=True,
        )
        DestinationCorrespondentOverride.objects.create(
            destination=destination,
            correspondent_org=corr,
            recipient_org=recipient,
            is_active=True,
        )

        resolved = resolve_correspondent_organizations(
            destination=destination,
            shipper_org=shipper,
            recipient_org=recipient,
        )
        self.assertEqual([org.id for org in resolved], [corr.id])

    def test_coordination_message_lists_other_correspondents(self):
        primary = self._create_org("Corr Principal", email="primary@example.org")
        other = self._create_org("Corr Secondaire", email="secondary@example.org")

        message = build_coordination_message_for_correspondent(
            current_correspondent=primary,
            all_correspondents=[primary, other],
        )

        self.assertIn("Corr Secondaire", message)
        self.assertIn("secondary@example.org", message)
        self.assertNotIn("Corr Principal", message)
