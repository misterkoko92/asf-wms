from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms import ScanOrderCreateForm, ScanShipmentForm
from wms.models import (
    Destination,
    DocumentRequirementTemplate,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipperScope,
)


class FormsOrgRolesGateTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str, correspondent: Contact) -> Destination:
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _assign_role(self, organization: Contact, role: str, *, is_active: bool = True):
        assignment, created = OrganizationRoleAssignment.objects.get_or_create(
            organization=organization,
            role=role,
            defaults={"is_active": is_active},
        )
        if not created and assignment.is_active != is_active:
            assignment.is_active = is_active
            assignment.save(update_fields=["is_active"])
        return assignment

    def _grant_shipper_scope(self, shipper: Contact, destination: Destination):
        assignment = self._assign_role(shipper, OrganizationRole.SHIPPER)
        ShipperScope.objects.create(
            role_assignment=assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        return assignment

    def _bind_recipient(self, shipper: Contact, recipient: Contact, destination: Destination):
        self._assign_role(recipient, OrganizationRole.RECIPIENT)
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=True,
        )

    def test_scan_order_create_form_stays_valid_without_legacy_runtime_gate(self):
        form = ScanOrderCreateForm(
            data={
                "shipper_name": "Shipper",
                "recipient_name": "Recipient",
                "correspondent_name": "",
                "shipper_contact": "",
                "recipient_contact": "",
                "correspondent_contact": "",
                "destination_address": "1 Rue Test",
                "destination_city": "Bamako",
                "destination_country": "Mali",
                "requested_delivery_date": "",
                "notes": "",
            }
        )

        self.assertTrue(form.is_valid())

    def test_scan_shipment_form_filters_recipients_from_bindings_when_engine_enabled(self):
        correspondent = self._create_org("Correspondent")
        destination = self._create_destination("BKO", correspondent)
        shipper = self._create_org("Shipper")
        recipient_allowed = self._create_org("Recipient Allowed")
        recipient_blocked = self._create_org("Recipient Blocked")
        self._grant_shipper_scope(shipper, destination)
        self._assign_role(recipient_allowed, OrganizationRole.RECIPIENT)
        self._assign_role(recipient_blocked, OrganizationRole.RECIPIENT)
        self._bind_recipient(shipper, recipient_allowed, destination)

        form = ScanShipmentForm(
            destination_id=str(destination.id),
            initial={"shipper_contact": str(shipper.id)},
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        self.assertIn(
            shipper.id, form.fields["shipper_contact"].queryset.values_list("id", flat=True)
        )
        self.assertIn(recipient_allowed.id, recipient_ids)
        self.assertNotIn(recipient_blocked.id, recipient_ids)

    def test_scan_shipment_form_filters_person_recipients_from_org_bindings_when_engine_enabled(
        self,
    ):
        correspondent = self._create_org("Correspondent Org Contact")
        destination = self._create_destination("LBV", correspondent)
        shipper_org = self._create_org("Shipper Org")
        recipient_allowed_org = self._create_org("Recipient Allowed Org")
        recipient_blocked_org = self._create_org("Recipient Blocked Org")
        shipper_contact = Contact.objects.create(
            name="Shipper Person",
            contact_type=ContactType.PERSON,
            first_name="Sam",
            last_name="Shipper",
            organization=shipper_org,
            is_active=True,
        )
        recipient_allowed_contact = Contact.objects.create(
            name="Recipient Allowed Person",
            contact_type=ContactType.PERSON,
            first_name="Ana",
            last_name="Allowed",
            organization=recipient_allowed_org,
            is_active=True,
        )
        recipient_blocked_contact = Contact.objects.create(
            name="Recipient Blocked Person",
            contact_type=ContactType.PERSON,
            first_name="Ben",
            last_name="Blocked",
            organization=recipient_blocked_org,
            is_active=True,
        )
        self._grant_shipper_scope(shipper_org, destination)
        self._assign_role(recipient_allowed_org, OrganizationRole.RECIPIENT)
        self._assign_role(recipient_blocked_org, OrganizationRole.RECIPIENT)
        self._bind_recipient(shipper_org, recipient_allowed_org, destination)

        form = ScanShipmentForm(
            destination_id=str(destination.id),
            initial={"shipper_contact": str(shipper_contact.id)},
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        self.assertIn(recipient_allowed_contact.id, recipient_ids)
        self.assertNotIn(recipient_blocked_contact.id, recipient_ids)

    def test_scan_shipment_form_keeps_all_shippers_selectable_when_engine_enabled(self):
        correspondent = self._create_org("Correspondent Scope")
        destination = self._create_destination("CMN", correspondent)
        other_destination = self._create_destination("NBO", correspondent)
        shipper_in_scope = self._create_org("Shipper In Scope")
        shipper_out_scope = self._create_org("Shipper Out Scope")
        recipient = self._create_org("Recipient Scope")
        self._grant_shipper_scope(shipper_in_scope, destination)
        self._grant_shipper_scope(shipper_out_scope, other_destination)
        self._assign_role(recipient, OrganizationRole.RECIPIENT)
        self._bind_recipient(shipper_in_scope, recipient, destination)

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_out_scope.id),
                "recipient_contact": str(recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            },
            destination_id=str(destination.id),
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        self.assertIn(shipper_in_scope.id, shipper_ids)
        self.assertIn(shipper_out_scope.id, shipper_ids)
        self.assertFalse(form.is_valid())
        self.assertTrue(
            any(
                "escale" in error.lower() or "destination" in error.lower()
                for error in form.errors.get("shipper_contact", [])
            )
        )

    def test_scan_shipment_form_blocks_recipient_pending_review_or_non_compliant(self):
        correspondent = self._create_org("Correspondent DLA")
        destination = self._create_destination("DLA", correspondent)

        shipper = self._create_org("Shipper DLA")
        recipient = self._create_org("Recipient DLA")
        self._grant_shipper_scope(shipper, destination)
        recipient_assignment = self._assign_role(
            recipient,
            OrganizationRole.RECIPIENT,
            is_active=False,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient,
            destination=destination,
            is_active=True,
        )

        form_pending = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
                "recipient_contact": str(recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            },
            destination_id=str(destination.id),
        )
        self.assertFalse(form_pending.is_valid())
        self.assertTrue(
            any(
                "revue" in error.lower()
                for error in form_pending.errors.get("recipient_contact", [])
            )
        )

        recipient_primary_contact = OrganizationContact.objects.create(
            organization=recipient,
            first_name="Recipient",
            last_name="Primary",
            email="recipient-primary@example.org",
            is_active=True,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=recipient_assignment,
            contact=recipient_primary_contact,
            is_primary=True,
            is_active=True,
        )
        recipient_assignment.is_active = True
        recipient_assignment.save(update_fields=["is_active"])
        DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.RECIPIENT,
            code="recipient-legal-doc",
            label="Doc recipient",
            is_required=True,
            is_active=True,
        )

        form_non_compliant = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
                "recipient_contact": str(recipient.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            },
            destination_id=str(destination.id),
        )
        self.assertFalse(form_non_compliant.is_valid())
        self.assertTrue(
            any(
                "conforme" in error.lower() or "document" in error.lower()
                for error in form_non_compliant.errors.get("recipient_contact", [])
            )
        )

    def test_scan_shipment_form_lists_shipper_and_recipient_without_legacy_tags(self):
        correspondent = self._create_org("Correspondent Org Roles Only")
        destination = self._create_destination("LOS", correspondent)
        shipper = self._create_org("Shipper Org Roles Only")
        recipient_allowed = self._create_org("Recipient Allowed Org Roles Only")
        recipient_blocked = self._create_org("Recipient Blocked Org Roles Only")

        shipper_assignment = OrganizationRoleAssignment.objects.create(
            organization=shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_allowed,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=recipient_blocked,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        ShipperScope.objects.create(
            role_assignment=shipper_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper,
            recipient_org=recipient_allowed,
            destination=destination,
            is_active=True,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper.id),
            },
            destination_id=str(destination.id),
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))

        self.assertIn(shipper.id, shipper_ids)
        self.assertIn(recipient_allowed.id, recipient_ids)
        self.assertNotIn(recipient_blocked.id, recipient_ids)
