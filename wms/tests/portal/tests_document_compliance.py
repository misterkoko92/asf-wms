from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.compliance import (
    can_bypass_with_override,
    is_role_compliant,
    is_role_operation_allowed,
    list_compliance_override_reminders,
)
from wms.models import (
    ComplianceOverride,
    DocumentRequirementTemplate,
    DocumentReviewStatus,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    OrganizationRoleDocument,
)


class DocumentComplianceTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_role_assignment(self, organization: Contact) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=organization,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )

    def _create_primary_role_contact(
        self, assignment: OrganizationRoleAssignment, email: str
    ) -> OrganizationRoleContact:
        contact = OrganizationContact.objects.create(
            organization=assignment.organization,
            first_name="Primary",
            last_name="Contact",
            email=email,
            is_active=True,
        )
        return OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=contact,
            is_primary=True,
            is_active=True,
        )

    def test_override_requires_expiration_and_reason(self):
        org = self._create_org("Org Override")
        assignment = self._create_role_assignment(org)

        with self.assertRaises(ValidationError) as missing_expiration:
            ComplianceOverride(
                role_assignment=assignment,
                reason="Validation temporaire",
                expires_at=None,
            ).full_clean()
        self.assertIn("expires_at", missing_expiration.exception.message_dict)

        with self.assertRaises(ValidationError) as missing_reason:
            ComplianceOverride(
                role_assignment=assignment,
                reason="",
                expires_at=timezone.now() + timedelta(days=2),
            ).full_clean()
        self.assertIn("reason", missing_reason.exception.message_dict)

    def test_is_role_compliant_requires_all_required_documents_approved(self):
        org = self._create_org("Org Compliance")
        assignment = self._create_role_assignment(org)
        required = DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.SHIPPER,
            code="id_legal",
            label="Piece legale",
            is_required=True,
            is_active=True,
        )
        DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.SHIPPER,
            code="optional_info",
            label="Info optionnelle",
            is_required=False,
            is_active=True,
        )

        self.assertFalse(is_role_compliant(assignment))

        role_doc = OrganizationRoleDocument.objects.create(
            role_assignment=assignment,
            requirement_template=required,
            status=DocumentReviewStatus.PENDING,
            is_active=True,
        )
        self.assertFalse(is_role_compliant(assignment))

        role_doc.status = DocumentReviewStatus.APPROVED
        role_doc.save(update_fields=["status"])
        self.assertTrue(is_role_compliant(assignment))

    def test_is_role_operation_allowed_uses_compliance_or_override(self):
        org = self._create_org("Org Ops")
        assignment = self._create_role_assignment(org)
        DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.SHIPPER,
            code="doc_required",
            label="Doc obligatoire",
            is_required=True,
            is_active=True,
        )

        self.assertFalse(is_role_operation_allowed(assignment))

        ComplianceOverride.objects.create(
            role_assignment=assignment,
            reason="Autorisation temporaire",
            expires_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        self.assertTrue(can_bypass_with_override(assignment))
        self.assertTrue(is_role_operation_allowed(assignment))

    def test_list_compliance_override_reminders_targets_j3_and_j1(self):
        User = get_user_model()
        User.objects.create_user(
            username="admin-compliance",
            email="admin@example.org",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )

        org = self._create_org("Org Reminder")
        assignment = self._create_role_assignment(org)
        self._create_primary_role_contact(assignment, "primary@example.org")

        now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        override_j3 = ComplianceOverride.objects.create(
            role_assignment=assignment,
            reason="Override J3",
            expires_at=now + timedelta(days=3),
            is_active=True,
        )
        ComplianceOverride.objects.create(
            role_assignment=assignment,
            reason="Override J2",
            expires_at=now + timedelta(days=2),
            is_active=True,
        )
        override_j1 = ComplianceOverride.objects.create(
            role_assignment=assignment,
            reason="Override J1",
            expires_at=now + timedelta(days=1),
            is_active=True,
        )

        reminders = list_compliance_override_reminders(now=now)
        reminder_by_id = {item["override"].id: item for item in reminders}

        self.assertEqual(set(reminder_by_id), {override_j3.id, override_j1.id})
        self.assertEqual(reminder_by_id[override_j3.id]["days_left"], 3)
        self.assertEqual(reminder_by_id[override_j1.id]["days_left"], 1)
        self.assertEqual(
            reminder_by_id[override_j3.id]["recipients"],
            ["admin@example.org", "primary@example.org"],
        )
