from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    RecipientBinding,
    ShipperScope,
    WmsRuntimeSettings,
)


class ScanAdminContactsCockpitViewTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="scan-cockpit-superuser",
            password="pass1234",
            email="scan-cockpit-superuser@example.com",
        )
        self.correspondent = Contact.objects.create(
            name="Correspondent Test",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = Destination.objects.create(
            city="Bamako",
            iata_code="BKO",
            country="Mali",
            correspondent_contact=self.correspondent,
            is_active=True,
        )
        self.shipper = Contact.objects.create(
            name="Shipper Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.recipient = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.other_org = Contact.objects.create(
            name="Other Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=self.shipper,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )
        OrganizationRoleAssignment.objects.create(
            organization=self.recipient,
            role=OrganizationRole.RECIPIENT,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=self.shipper,
            recipient_org=self.recipient,
            destination=self.destination,
            is_active=True,
        )

    def _create_primary_role_contact(self, *, assignment):
        org_contact = OrganizationContact.objects.create(
            organization=assignment.organization,
            first_name="Primary",
            last_name="Contact",
            email="primary@example.org",
            is_active=True,
        )
        return OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=org_contact,
            is_primary=True,
            is_active=True,
        )

    def test_scan_admin_contacts_renders_org_role_cockpit(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pilotage contacts org-role")
        self.assertContains(response, "Recherche et filtres")
        self.assertContains(response, "Actions metier")
        self.assertEqual(response.context["active"], "admin_contacts")

    def test_filter_by_role_returns_only_matching_orgs(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("scan:scan_admin_contacts"), {"role": "recipient"})

        self.assertEqual(response.status_code, 200)
        rows = response.context["cockpit_rows"]
        self.assertEqual([row["organization"].id for row in rows], [self.recipient.id])

    def test_filter_by_shipper_org_returns_linked_recipients(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("scan:scan_admin_contacts"),
            {
                "role": "recipient",
                "shipper_org_id": str(self.shipper.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        rows = response.context["cockpit_rows"]
        self.assertEqual([row["organization"].id for row in rows], [self.recipient.id])

    def test_assign_role_requires_primary_email_contact(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "assign_role",
                "organization_id": str(self.other_org.id),
                "role": OrganizationRole.SHIPPER,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "contact principal actif")
        assignment = OrganizationRoleAssignment.objects.get(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
        )
        self.assertFalse(assignment.is_active)

    def test_assign_role_activates_when_primary_email_contact_exists(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        self._create_primary_role_contact(assignment=assignment)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "assign_role",
                "organization_id": str(self.other_org.id),
                "role": OrganizationRole.SHIPPER,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

    def test_unassign_role_deactivates_assignment(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "unassign_role",
                "organization_id": str(self.other_org.id),
                "role": OrganizationRole.SHIPPER,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_upsert_org_contact_creates_new_contact(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_org_contact",
                "organization_id": str(self.other_org.id),
                "first_name": "Aya",
                "last_name": "Diallo",
                "email": "aya.diallo@example.org",
                "phone": "+22370000000",
                "is_active": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            OrganizationContact.objects.filter(
                organization=self.other_org,
                first_name="Aya",
                last_name="Diallo",
                email="aya.diallo@example.org",
                is_active=True,
            ).exists()
        )

    def test_link_role_contact_rejects_contact_from_other_org(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        external_contact = OrganizationContact.objects.create(
            organization=self.shipper,
            first_name="External",
            last_name="Contact",
            email="external@example.org",
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "link_role_contact",
                "role_assignment_id": str(assignment.id),
                "organization_contact_id": str(external_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "meme organisation")
        self.assertFalse(
            OrganizationRoleContact.objects.filter(
                role_assignment=assignment,
                contact=external_contact,
            ).exists()
        )

    def test_link_role_contact_creates_active_link(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        org_contact = OrganizationContact.objects.create(
            organization=self.other_org,
            first_name="Link",
            last_name="Contact",
            email="link@example.org",
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "link_role_contact",
                "role_assignment_id": str(assignment.id),
                "organization_contact_id": str(org_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            OrganizationRoleContact.objects.filter(
                role_assignment=assignment,
                contact=org_contact,
                is_active=True,
            ).exists()
        )

    def test_set_primary_role_contact_switches_primary_contact(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        first_contact = OrganizationContact.objects.create(
            organization=self.other_org,
            first_name="First",
            last_name="Primary",
            email="first.primary@example.org",
            is_active=True,
        )
        second_contact = OrganizationContact.objects.create(
            organization=self.other_org,
            first_name="Second",
            last_name="Primary",
            email="second.primary@example.org",
            is_active=True,
        )
        first_link = OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=first_contact,
            is_primary=True,
            is_active=True,
        )
        second_link = OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=second_contact,
            is_primary=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "set_primary_role_contact",
                "role_assignment_id": str(assignment.id),
                "organization_contact_id": str(second_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        first_link.refresh_from_db()
        second_link.refresh_from_db()
        self.assertFalse(first_link.is_primary)
        self.assertTrue(second_link.is_primary)

    def test_unlink_role_contact_deactivates_link(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        org_contact = OrganizationContact.objects.create(
            organization=self.other_org,
            first_name="Inactive",
            last_name="Target",
            email="inactive.target@example.org",
            is_active=True,
        )
        role_contact = OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=org_contact,
            is_primary=True,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "unlink_role_contact",
                "role_assignment_id": str(assignment.id),
                "organization_contact_id": str(org_contact.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        role_contact.refresh_from_db()
        self.assertFalse(role_contact.is_active)
        self.assertFalse(role_contact.is_primary)

    def test_upsert_shipper_scope_creates_global_scope(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_shipper_scope",
                "role_assignment_id": str(assignment.id),
                "all_destinations": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=assignment,
                all_destinations=True,
                is_active=True,
            ).exists()
        )

    def test_upsert_shipper_scope_defaults_to_global_when_destination_empty(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_shipper_scope",
                "role_assignment_id": str(assignment.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        scope = ShipperScope.objects.filter(role_assignment=assignment).first()
        self.assertIsNotNone(scope)
        self.assertTrue(scope.all_destinations)
        self.assertIsNone(scope.destination)

    def test_upsert_shipper_scope_creates_destination_scope(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_shipper_scope",
                "role_assignment_id": str(assignment.id),
                "destination_id": str(self.destination.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=assignment,
                destination=self.destination,
                all_destinations=False,
                is_active=True,
            ).exists()
        )

    def test_upsert_shipper_scope_requires_global_xor_destination(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_shipper_scope",
                "role_assignment_id": str(assignment.id),
                "all_destinations": "1",
                "destination_id": str(self.destination.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "soit toutes les escales, soit une escale cible")
        self.assertFalse(ShipperScope.objects.filter(role_assignment=assignment).exists())

    def test_disable_shipper_scope_deactivates_scope(self):
        self.client.force_login(self.superuser)
        assignment = OrganizationRoleAssignment.objects.create(
            organization=self.other_org,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        scope = ShipperScope.objects.create(
            role_assignment=assignment,
            destination=self.destination,
            all_destinations=False,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "disable_shipper_scope",
                "scope_id": str(scope.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        scope.refresh_from_db()
        self.assertFalse(scope.is_active)

    def test_upsert_recipient_binding_creates_active_binding(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_recipient_binding",
                "shipper_org_id": str(self.shipper.id),
                "recipient_org_id": str(self.other_org.id),
                "destination_id": str(self.destination.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=self.shipper,
                recipient_org=self.other_org,
                destination=self.destination,
                is_active=True,
            ).exists()
        )

    def test_close_recipient_binding_sets_valid_to_and_inactive(self):
        self.client.force_login(self.superuser)
        binding = RecipientBinding.objects.create(
            shipper_org=self.shipper,
            recipient_org=self.other_org,
            destination=self.destination,
            is_active=True,
        )

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "close_recipient_binding",
                "binding_id": str(binding.id),
                "valid_to": "2030-01-01T10:00",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        binding.refresh_from_db()
        self.assertFalse(binding.is_active)
        self.assertIsNotNone(binding.valid_to)

    def test_upsert_recipient_binding_rejects_invalid_validity_window(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_recipient_binding",
                "shipper_org_id": str(self.shipper.id),
                "recipient_org_id": str(self.other_org.id),
                "destination_id": str(self.destination.id),
                "valid_from": "2030-01-02T10:00",
                "valid_to": "2030-01-01T10:00",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La fin de validite doit etre posterieure au debut.")
        self.assertFalse(
            RecipientBinding.objects.filter(
                shipper_org=self.shipper,
                recipient_org=self.other_org,
                destination=self.destination,
                valid_from__year=2030,
            ).exists()
        )

    def test_create_guided_contact_creates_organization_and_role_assignment(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_guided_contact",
                "entity_kind": "organization",
                "organization_name": "Guided Org",
                "role": OrganizationRole.SHIPPER,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        organization = Contact.objects.filter(
            name="Guided Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ).first()
        self.assertIsNotNone(organization)
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(
                organization=organization,
                role=OrganizationRole.SHIPPER,
            ).exists()
        )

    def test_create_guided_contact_creates_person_linked_to_existing_org(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_guided_contact",
                "entity_kind": "person",
                "organization_id": str(self.other_org.id),
                "name": "Aya Diallo",
                "first_name": "Aya",
                "last_name": "Diallo",
                "email": "aya.diallo@example.org",
                "phone": "+22370010000",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Contact.objects.filter(
                contact_type=ContactType.PERSON,
                organization=self.other_org,
                first_name="Aya",
                last_name="Diallo",
                email="aya.diallo@example.org",
                phone="+22370010000",
                is_active=True,
            ).exists()
        )

    def test_create_guided_org_with_person_payload_creates_primary_org_contact(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_guided_contact",
                "entity_kind": "organization",
                "organization_name": "Guided Primary Org",
                "role": OrganizationRole.SHIPPER,
                "name": "Nina Role",
                "first_name": "Nina",
                "last_name": "Role",
                "email": "nina.role@example.org",
                "phone": "+33102030405",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        organization = Contact.objects.filter(
            name="Guided Primary Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        ).first()
        self.assertIsNotNone(organization)
        assignment = OrganizationRoleAssignment.objects.filter(
            organization=organization,
            role=OrganizationRole.SHIPPER,
        ).first()
        self.assertIsNotNone(assignment)
        org_contact = OrganizationContact.objects.filter(
            organization=organization,
            first_name="Nina",
            last_name="Role",
            email="nina.role@example.org",
            phone="+33102030405",
            is_active=True,
        ).first()
        self.assertIsNotNone(org_contact)
        self.assertTrue(
            OrganizationRoleContact.objects.filter(
                role_assignment=assignment,
                contact=org_contact,
                is_primary=True,
                is_active=True,
            ).exists()
        )

    def test_legacy_actions_blocked_when_runtime_flag_disabled(self):
        self.client.force_login(self.superuser)
        runtime = WmsRuntimeSettings.get_solo()
        runtime.legacy_contact_write_enabled = False
        runtime.save(update_fields=["legacy_contact_write_enabled"])

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "create_contact",
                "q": "",
                "contact_type": "all",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mode legacy desactive")

    def test_cockpit_forms_render_when_legacy_write_disabled(self):
        self.client.force_login(self.superuser)
        runtime = WmsRuntimeSettings.get_solo()
        runtime.legacy_contact_write_enabled = False
        runtime.save(update_fields=["legacy_contact_write_enabled"])

        response = self.client.get(reverse("scan:scan_admin_contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="action" value="assign_role"')
        self.assertContains(response, 'name="action" value="upsert_org_contact"')
        self.assertContains(response, 'name="action" value="upsert_shipper_scope"')
        self.assertContains(response, 'name="action" value="upsert_recipient_binding"')
        self.assertContains(response, 'name="action" value="create_guided_contact"')
        self.assertNotContains(response, 'name="action" value="create_contact"')

    def test_org_role_action_still_works_when_legacy_write_disabled(self):
        self.client.force_login(self.superuser)
        runtime = WmsRuntimeSettings.get_solo()
        runtime.legacy_contact_write_enabled = False
        runtime.save(update_fields=["legacy_contact_write_enabled"])

        response = self.client.post(
            reverse("scan:scan_admin_contacts"),
            {
                "action": "upsert_org_contact",
                "organization_id": str(self.other_org.id),
                "first_name": "Nina",
                "last_name": "Role",
                "email": "nina.role@example.org",
                "is_active": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            OrganizationContact.objects.filter(
                organization=self.other_org,
                first_name="Nina",
                last_name="Role",
                email="nina.role@example.org",
                is_active=True,
            ).exists()
        )
