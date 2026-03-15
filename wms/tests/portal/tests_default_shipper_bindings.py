from django.test import TestCase

from contacts.models import Contact, ContactTag, ContactType
from wms.default_shipper_bindings import (
    _ensure_bindings_for_pairs,
    _ensure_default_shipper_assignment_and_scope,
    _resolve_default_shipper_organization,
    ensure_default_shipper_bindings_for_destination_id,
    ensure_default_shipper_bindings_for_recipient_assignment_id,
)
from wms.models import (
    Destination,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipperScope,
)


class DefaultShipperBindingsSignalTests(TestCase):
    def _create_default_shipper(self) -> Contact:
        shipper = Contact.objects.create(
            name="AVIATION SANS FRONTIERES",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        shipper_tag, _ = ContactTag.objects.get_or_create(name="expediteur")
        shipper.tags.add(shipper_tag)
        return shipper

    def _create_correspondent(self) -> Contact:
        correspondent = Contact.objects.create(
            name="Correspondent",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        correspondent_tag, _ = ContactTag.objects.get_or_create(name="correspondant")
        correspondent.tags.add(correspondent_tag)
        return correspondent

    def _create_destination(self, *, iata_code: str, correspondent: Contact) -> Destination:
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient_org(self, name: str) -> Contact:
        recipient = Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        recipient_tag, _ = ContactTag.objects.get_or_create(name="destinataire")
        recipient.tags.add(recipient_tag)
        return recipient

    def test_recipient_role_creation_creates_default_shipper_bindings_for_all_destinations(
        self,
    ):
        default_shipper = self._create_default_shipper()
        correspondent = self._create_correspondent()
        destination_a = self._create_destination(iata_code="ABJ", correspondent=correspondent)
        destination_b = self._create_destination(iata_code="DLA", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient A")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        shipper_assignment = OrganizationRoleAssignment.objects.filter(
            organization=default_shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        ).first()
        self.assertIsNotNone(shipper_assignment)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=shipper_assignment,
                all_destinations=True,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_a,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_b,
                is_active=True,
            ).exists()
        )

    def test_destination_creation_creates_binding_for_existing_recipients(self):
        default_shipper = self._create_default_shipper()
        correspondent = self._create_correspondent()
        destination_a = self._create_destination(iata_code="BKO", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient B")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_a,
                is_active=True,
            ).exists()
        )

        with self.captureOnCommitCallbacks(execute=True):
            destination_b = self._create_destination(
                iata_code="CMN",
                correspondent=correspondent,
            )

        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=default_shipper,
                recipient_org=recipient,
                destination=destination_b,
                is_active=True,
            ).exists()
        )

    def test_no_default_shipper_keeps_bindings_unchanged(self):
        correspondent = self._create_correspondent()
        self._create_destination(iata_code="TNR", correspondent=correspondent)
        recipient = self._create_recipient_org("Recipient C")

        with self.captureOnCommitCallbacks(execute=True):
            OrganizationRoleAssignment.objects.create(
                organization=recipient,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
            )

        self.assertEqual(RecipientBinding.objects.count(), 0)


class DefaultShipperBindingsHelpersTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_default_shipper(self) -> Contact:
        shipper = self._create_org("AVIATION SANS FRONTIERES")
        shipper_tag, _ = ContactTag.objects.get_or_create(name="expediteur")
        shipper.tags.add(shipper_tag)
        return shipper

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_org(f"Correspondent {iata}")
        correspondent_tag, _ = ContactTag.objects.get_or_create(name="correspondant")
        correspondent.tags.add(correspondent_tag)
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_recipient_role_assignment(self, org: Contact) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=org,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )

    def test_resolve_default_shipper_returns_none_for_missing_or_inactive_defaults(self):
        with self.settings():
            self.assertIsNone(_resolve_default_shipper_organization())

        inactive_default_shipper = self._create_org("Inactive ASF")
        inactive_default_shipper_tag, _ = ContactTag.objects.get_or_create(name="expediteur")
        inactive_default_shipper.tags.add(inactive_default_shipper_tag)
        inactive_default_shipper.is_active = False
        inactive_default_shipper.save(update_fields=["is_active"])
        self.assertIsNone(_resolve_default_shipper_organization())

    def test_resolve_default_shipper_supports_person_linked_to_active_organization(self):
        organization = self._create_default_shipper()
        person = Contact.objects.create(
            name="ASF Person",
            contact_type=ContactType.PERSON,
            is_active=True,
            organization=organization,
        )
        shipper_tag, _ = ContactTag.objects.get_or_create(name="expediteur")
        person.tags.add(shipper_tag)

        resolved = _resolve_default_shipper_organization()
        self.assertEqual(resolved.pk, organization.pk)

        organization.is_active = False
        organization.save(update_fields=["is_active"])
        self.assertIsNone(_resolve_default_shipper_organization())

    def test_ensure_default_shipper_assignment_and_scope_reactivates_existing_records(self):
        shipper_org = self._create_default_shipper()
        assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        primary_contact = OrganizationContact.objects.create(
            organization=shipper_org,
            first_name="Primary",
            last_name="Shipper",
            email="shipper-primary@example.org",
            is_active=True,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=primary_contact,
            is_primary=True,
            is_active=True,
        )
        destination = self._create_destination("ABJ")
        scope = ShipperScope.objects.create(
            role_assignment=assignment,
            all_destinations=True,
            destination=None,
            is_active=False,
        )
        ShipperScope.objects.filter(pk=scope.pk).update(destination=destination)

        _ensure_default_shipper_assignment_and_scope(shipper_org)

        assignment.refresh_from_db()
        scope = ShipperScope.objects.get(role_assignment=assignment, all_destinations=True)
        self.assertTrue(assignment.is_active)
        self.assertTrue(scope.is_active)
        self.assertIsNone(scope.destination)

    def test_ensure_bindings_for_pairs_handles_empty_and_avoids_duplicates(self):
        shipper_org = self._create_default_shipper()
        destination = self._create_destination("CMN")
        recipient = self._create_org("Recipient")

        created = _ensure_bindings_for_pairs(
            shipper_org=shipper_org,
            recipient_org_ids=[],
            destination_ids=[destination.id],
        )
        self.assertEqual(created, 0)

        created = _ensure_bindings_for_pairs(
            shipper_org=shipper_org,
            recipient_org_ids=[recipient.id],
            destination_ids=[destination.id],
        )
        self.assertEqual(created, 1)

        created_again = _ensure_bindings_for_pairs(
            shipper_org=shipper_org,
            recipient_org_ids=[recipient.id],
            destination_ids=[destination.id],
        )
        self.assertEqual(created_again, 0)
        self.assertEqual(RecipientBinding.objects.count(), 1)

    def test_ensure_default_shipper_bindings_for_destination_id_guards_and_creates(self):
        shipper_org = self._create_default_shipper()
        recipient = self._create_org("Recipient Destination")
        self._create_recipient_role_assignment(recipient)
        destination = self._create_destination("DKR")
        correspondent = destination.correspondent_contact

        created_missing_destination = ensure_default_shipper_bindings_for_destination_id(999999)
        self.assertEqual(created_missing_destination, 0)

        created = ensure_default_shipper_bindings_for_destination_id(destination.id)
        self.assertEqual(created, 2)
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper_org,
                recipient_org=recipient,
                destination=destination,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper_org,
                recipient_org=correspondent,
                destination=destination,
                is_active=True,
            ).exists()
        )

    def test_ensure_default_shipper_bindings_for_recipient_assignment_id_guards_and_creates(
        self,
    ):
        shipper_org = self._create_default_shipper()
        recipient = self._create_org("Recipient Assignment")
        assignment = self._create_recipient_role_assignment(recipient)
        destination_a = self._create_destination("BKO")
        destination_b = self._create_destination("DLA")

        created_missing_assignment = ensure_default_shipper_bindings_for_recipient_assignment_id(
            999999
        )
        self.assertEqual(created_missing_assignment, 0)

        created = ensure_default_shipper_bindings_for_recipient_assignment_id(assignment.id)
        self.assertEqual(created, 2)
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper_org,
                recipient_org=recipient,
                destination=destination_a,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=shipper_org,
                recipient_org=recipient,
                destination=destination_b,
                is_active=True,
            ).exists()
        )
