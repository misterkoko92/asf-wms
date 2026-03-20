from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.forms import ScanOrderCreateForm, ScanShipmentForm
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipmentAuthorizedRecipientContact,
    ShipmentRecipientContact,
    ShipmentRecipientOrganization,
    ShipmentShipper,
    ShipmentShipperRecipientLink,
    ShipmentValidationStatus,
    ShipperScope,
)


class FormsOrgRolesGateTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_person(self, name: str, *, organization: Contact) -> Contact:
        first_name, _, last_name = name.partition(" ")
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.PERSON,
            first_name=first_name,
            last_name=last_name or first_name,
            organization=organization,
            is_active=True,
        )

    def _create_destination(self, iata: str, correspondent: Contact) -> Destination:
        destination = Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )
        ShipmentRecipientOrganization.objects.update_or_create(
            organization=correspondent.organization,
            defaults={
                "destination": destination,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_correspondent": True,
                "is_active": True,
            },
        )
        return destination

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
        organization = (
            shipper.organization if shipper.contact_type == ContactType.PERSON else shipper
        )
        assignment = self._assign_role(organization, OrganizationRole.SHIPPER)
        ShipperScope.objects.create(
            role_assignment=assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )
        shipper_record, _created = ShipmentShipper.objects.update_or_create(
            organization=organization,
            defaults={
                "default_contact": shipper,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_active": True,
            },
        )
        return shipper_record

    def _bind_recipient(
        self,
        shipper: Contact,
        recipient: Contact,
        destination: Destination,
        *,
        validation_status: str = ShipmentValidationStatus.VALIDATED,
    ):
        shipper_org = (
            shipper.organization if shipper.contact_type == ContactType.PERSON else shipper
        )
        recipient_org = (
            recipient.organization if recipient.contact_type == ContactType.PERSON else recipient
        )
        self._assign_role(recipient_org, OrganizationRole.RECIPIENT)
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )
        recipient_organization, _created = ShipmentRecipientOrganization.objects.update_or_create(
            organization=recipient_org,
            defaults={
                "destination": destination,
                "validation_status": validation_status,
                "is_active": True,
            },
        )
        shipment_recipient_contact, _created = ShipmentRecipientContact.objects.update_or_create(
            recipient_organization=recipient_organization,
            contact=recipient,
            defaults={"is_active": True},
        )
        link, _created = ShipmentShipperRecipientLink.objects.update_or_create(
            shipper=ShipmentShipper.objects.get(organization=shipper_org),
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )
        ShipmentAuthorizedRecipientContact.objects.update_or_create(
            link=link,
            recipient_contact=shipment_recipient_contact,
            defaults={"is_default": True, "is_active": True},
        )
        return shipment_recipient_contact.contact

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
        correspondent_org = self._create_org("Correspondent")
        correspondent = self._create_person("Corr BKO", organization=correspondent_org)
        destination = self._create_destination("BKO", correspondent)
        shipper_org = self._create_org("Shipper")
        shipper_contact = self._create_person("Sam Shipper", organization=shipper_org)
        recipient_allowed_org = self._create_org("Recipient Allowed")
        recipient_allowed_contact = self._create_person(
            "Ana Allowed",
            organization=recipient_allowed_org,
        )
        recipient_blocked_org = self._create_org("Recipient Blocked")
        recipient_blocked_contact = self._create_person(
            "Ben Blocked",
            organization=recipient_blocked_org,
        )
        self._grant_shipper_scope(shipper_contact, destination)
        self._bind_recipient(shipper_contact, recipient_allowed_contact, destination)

        form = ScanShipmentForm(
            destination_id=str(destination.id),
            initial={"shipper_contact": str(shipper_contact.id)},
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        self.assertIn(shipper_contact.id, shipper_ids)
        self.assertIn(recipient_allowed_contact.id, recipient_ids)
        self.assertNotIn(recipient_blocked_contact.id, recipient_ids)

    def test_scan_shipment_form_filters_person_recipients_from_org_bindings_when_engine_enabled(
        self,
    ):
        correspondent_org = self._create_org("Correspondent Org Contact")
        correspondent = self._create_person("Corr LBV", organization=correspondent_org)
        destination = self._create_destination("LBV", correspondent)
        shipper_org = self._create_org("Shipper Org")
        shipper_contact = self._create_person("Sam Shipper", organization=shipper_org)
        recipient_allowed_org = self._create_org("Recipient Allowed Org")
        recipient_allowed_contact = self._create_person(
            "Ana Allowed",
            organization=recipient_allowed_org,
        )
        recipient_blocked_org = self._create_org("Recipient Blocked Org")
        recipient_blocked_contact = self._create_person(
            "Ben Blocked",
            organization=recipient_blocked_org,
        )
        self._grant_shipper_scope(shipper_contact, destination)
        self._bind_recipient(shipper_contact, recipient_allowed_contact, destination)

        form = ScanShipmentForm(
            destination_id=str(destination.id),
            initial={"shipper_contact": str(shipper_contact.id)},
        )

        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
        self.assertIn(recipient_allowed_contact.id, recipient_ids)
        self.assertNotIn(recipient_blocked_contact.id, recipient_ids)

    def test_scan_shipment_form_keeps_all_shippers_selectable_when_engine_enabled(self):
        correspondent_org = self._create_org("Correspondent Scope")
        correspondent = self._create_person("Corr CMN", organization=correspondent_org)
        destination = self._create_destination("CMN", correspondent)
        other_destination = self._create_destination("NBO", correspondent)
        shipper_in_scope_org = self._create_org("Shipper In Scope")
        shipper_in_scope_contact = self._create_person(
            "Shipper InScope",
            organization=shipper_in_scope_org,
        )
        shipper_out_scope_org = self._create_org("Shipper Out Scope")
        shipper_out_scope_contact = self._create_person(
            "Shipper OutScope",
            organization=shipper_out_scope_org,
        )
        recipient_org = self._create_org("Recipient Scope")
        recipient_contact = self._create_person("Recipient Scope", organization=recipient_org)
        self._grant_shipper_scope(shipper_in_scope_contact, destination)
        self._grant_shipper_scope(shipper_out_scope_contact, other_destination)
        self._bind_recipient(shipper_in_scope_contact, recipient_contact, destination)

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_out_scope_contact.id),
                "recipient_contact": str(recipient_contact.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            },
            destination_id=str(destination.id),
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        self.assertIn(shipper_in_scope_contact.id, shipper_ids)
        self.assertNotIn(shipper_out_scope_contact.id, shipper_ids)
        form.fields["shipper_contact"].queryset = Contact.objects.all()
        form.fields["recipient_contact"].queryset = Contact.objects.all()
        form.fields["correspondent_contact"].queryset = Contact.objects.all()

        self.assertFalse(form.is_valid())
        self.assertTrue(
            any(
                "escale" in error.lower() or "destination" in error.lower()
                for error in form.errors.get("shipper_contact", [])
            )
        )

    def test_scan_shipment_form_blocks_recipient_pending_review_or_non_compliant(self):
        correspondent_org = self._create_org("Correspondent DLA")
        correspondent = self._create_person("Corr DLA", organization=correspondent_org)
        destination = self._create_destination("DLA", correspondent)

        shipper_org = self._create_org("Shipper DLA")
        shipper_contact = self._create_person("Shipper DLA", organization=shipper_org)
        recipient_org = self._create_org("Recipient DLA")
        recipient_contact = self._create_person("Recipient DLA", organization=recipient_org)
        self._grant_shipper_scope(shipper_contact, destination)
        self._bind_recipient(
            shipper_contact,
            recipient_contact,
            destination,
            validation_status=ShipmentValidationStatus.PENDING,
        )

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
                "recipient_contact": str(recipient_contact.id),
                "correspondent_contact": str(correspondent.id),
                "carton_count": "1",
            },
            destination_id=str(destination.id),
        )

        self.assertFalse(form.is_valid())
        self.assertTrue(
            any("disponible" in error.lower() for error in form.errors.get("recipient_contact", []))
        )

    def test_scan_shipment_form_lists_shipper_and_recipient_without_legacy_tags(self):
        correspondent_org = self._create_org("Correspondent Org Roles Only")
        correspondent = self._create_person("Corr LOS", organization=correspondent_org)
        destination = self._create_destination("LOS", correspondent)
        shipper_org = self._create_org("Shipper Org Roles Only")
        shipper_contact = self._create_person("Sam LOS", organization=shipper_org)
        recipient_allowed_org = self._create_org("Recipient Allowed Org Roles Only")
        recipient_allowed_contact = self._create_person(
            "Ana LOS",
            organization=recipient_allowed_org,
        )
        recipient_blocked_org = self._create_org("Recipient Blocked Org Roles Only")
        recipient_blocked_contact = self._create_person(
            "Ben LOS",
            organization=recipient_blocked_org,
        )
        self._grant_shipper_scope(shipper_contact, destination)
        self._bind_recipient(shipper_contact, recipient_allowed_contact, destination)

        form = ScanShipmentForm(
            data={
                "destination": str(destination.id),
                "shipper_contact": str(shipper_contact.id),
            },
            destination_id=str(destination.id),
        )

        shipper_ids = set(form.fields["shipper_contact"].queryset.values_list("id", flat=True))
        recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))

        self.assertIn(shipper_contact.id, shipper_ids)
        self.assertIn(recipient_allowed_contact.id, recipient_ids)
        self.assertNotIn(recipient_blocked_contact.id, recipient_ids)
