from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone

from contacts.models import Contact, ContactAddress, ContactType
from wms.admin_account_request_approval import approve_account_request
from wms.models import (
    AssociationProfile,
    AssociationRecipient,
    ComplianceOverride,
    Destination,
    DocumentRequirementTemplate,
    OrganizationContact,
    OrganizationRole,
    OrganizationRoleAssignment,
    OrganizationRoleContact,
    PublicAccountRequest,
    PublicAccountRequestStatus,
    PublicAccountRequestType,
    RecipientBinding,
    ShipperScope,
)
from wms.view_permissions import (
    BLOCKED_REASON_COMPLIANCE_REQUIRED,
    BLOCKED_REASON_QUERY_PARAM,
    BLOCKED_REASON_REVIEW_PENDING,
)


class PortalRoleReviewGateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="portal-role-gate",
            email="portal-role-gate@example.org",
            password="pass1234",
        )
        self.contact = Contact.objects.create(
            name="Association Role Gate",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email=self.user.email,
        )
        ContactAddress.objects.create(
            contact=self.contact,
            address_line1="1 Rue Role Gate",
            city="Paris",
            postal_code="75001",
            country="France",
            is_default=True,
        )
        self.profile = AssociationProfile.objects.create(
            user=self.user,
            contact=self.contact,
            must_change_password=False,
        )
        self.client.force_login(self.user)

        self.recipients_url = reverse("portal:portal_recipients")
        self.order_create_url = reverse("portal:portal_order_create")
        self.account_url = reverse("portal:portal_account")

        self.destination = self._create_destination("BKO")
        self._create_delivery_recipient(
            structure_name="Destinataire Livraison",
            destination=self.destination,
        )

    def _create_destination(self, iata_code: str) -> Destination:
        correspondent = Contact.objects.create(
            name=f"Correspondant {iata_code}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        return Destination.objects.create(
            city=f"City {iata_code}",
            iata_code=iata_code,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_delivery_recipient(self, *, structure_name: str, destination: Destination):
        return AssociationRecipient.objects.create(
            association_contact=self.profile.contact,
            destination=destination,
            name=structure_name,
            structure_name=structure_name,
            address_line1="1 Rue Livraison",
            city=destination.city,
            country=destination.country,
            is_delivery_contact=True,
            is_active=True,
        )

    def _activate_shipper_assignment(self) -> OrganizationRoleAssignment:
        assignment, _ = OrganizationRoleAssignment.objects.get_or_create(
            organization=self.profile.contact,
            role=OrganizationRole.SHIPPER,
            defaults={"is_active": False},
        )
        contact = OrganizationContact.objects.create(
            organization=self.profile.contact,
            first_name="Primary",
            last_name="Gate",
            email="primary-gate@example.org",
            is_active=True,
        )
        OrganizationRoleContact.objects.create(
            role_assignment=assignment,
            contact=contact,
            is_primary=True,
            is_active=True,
        )
        assignment.is_active = True
        assignment.save(update_fields=["is_active"])
        return assignment

    def test_shipper_pending_review_blocks_order_creation(self):
        OrganizationRoleAssignment.objects.create(
            organization=self.profile.contact,
            role=OrganizationRole.SHIPPER,
            is_active=False,
        )
        response = self.client.get(self.order_create_url, follow=True)
        expected_redirect = (
            f"{self.account_url}?{BLOCKED_REASON_QUERY_PARAM}={BLOCKED_REASON_REVIEW_PENDING}"
        )
        self.assertRedirects(response, expected_redirect)
        self.assertContains(response, "Compte expéditeur en cours de revue ASF")

    def test_non_compliant_shipper_blocks_order_creation(self):
        assignment = self._activate_shipper_assignment()
        DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.SHIPPER,
            code="legal-doc",
            label="Document légal",
            is_required=True,
            is_active=True,
        )

        response = self.client.get(self.order_create_url, follow=True)
        expected_redirect = (
            f"{self.account_url}?{BLOCKED_REASON_QUERY_PARAM}={BLOCKED_REASON_COMPLIANCE_REQUIRED}"
        )
        self.assertRedirects(response, expected_redirect)
        self.assertContains(response, "documents expéditeur non conformes")
        self.assertTrue(
            OrganizationRoleAssignment.objects.filter(pk=assignment.pk, is_active=True).exists()
        )

    def test_compliance_override_unblocks_order_creation(self):
        assignment = self._activate_shipper_assignment()
        DocumentRequirementTemplate.objects.create(
            role=OrganizationRole.SHIPPER,
            code="legal-doc-2",
            label="Document légal 2",
            is_required=True,
            is_active=True,
        )
        ComplianceOverride.objects.create(
            role_assignment=assignment,
            reason="Override temporaire",
            expires_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )

        response = self.client.get(self.order_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portal/order_create.html")

    def test_recipient_creation_creates_active_recipient_role_assignment(self):
        destination = self._create_destination("DLA")
        response = self.client.post(
            self.recipients_url,
            {
                "action": "create_recipient",
                "destination_id": str(destination.id),
                "structure_name": "Action contre la faim",
                "contact_title": "",
                "contact_last_name": "",
                "contact_first_name": "",
                "phones": "",
                "emails": "ops-acf@example.org",
                "address_line1": "1 Avenue Recipient",
                "address_line2": "",
                "postal_code": "",
                "city": "Douala",
                "country": "Cameroun",
                "notes": "",
                "notify_deliveries": "",
                "is_delivery_contact": "",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        recipient = AssociationRecipient.objects.get(structure_name="Action contre la faim")
        self.assertIsNotNone(recipient.synced_contact_id)
        recipient_contact = recipient.synced_contact
        assignment = OrganizationRoleAssignment.objects.filter(
            organization=recipient_contact,
            role=OrganizationRole.RECIPIENT,
        ).first()
        shipper_assignment = OrganizationRoleAssignment.objects.filter(
            organization=self.profile.contact,
            role=OrganizationRole.SHIPPER,
        ).first()
        self.assertIsNotNone(assignment)
        self.assertIsNotNone(shipper_assignment)
        self.assertTrue(assignment.is_active)
        self.assertTrue(
            ShipperScope.objects.filter(
                role_assignment=shipper_assignment,
                destination=destination,
                all_destinations=False,
                is_active=True,
            ).exists()
        )
        self.assertTrue(
            RecipientBinding.objects.filter(
                shipper_org=self.profile.contact,
                recipient_org=recipient_contact,
                destination=destination,
                is_active=True,
            ).exists()
        )

    def test_approve_account_request_activates_shipper_role_assignment(self):
        admin_user = get_user_model().objects.create_user(
            username="admin-role-review",
            email="admin-role-review@example.org",
            password="pass1234",
            is_staff=True,
            is_superuser=True,
        )
        account_request = PublicAccountRequest.objects.create(
            account_type=PublicAccountRequestType.ASSOCIATION,
            status=PublicAccountRequestStatus.PENDING,
            association_name="Association Review Pending",
            email="new-association@example.org",
            phone="",
            address_line1="1 Rue Pending",
            address_line2="",
            postal_code="",
            city="Paris",
            country="France",
        )
        request = RequestFactory().post("/admin/wms/publicaccountrequest/")
        request.user = admin_user

        ok, reason = approve_account_request(
            request=request,
            account_request=account_request,
            enqueue_email=lambda **kwargs: None,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        account_request.refresh_from_db()
        self.assertEqual(account_request.status, PublicAccountRequestStatus.APPROVED)
        assignment = OrganizationRoleAssignment.objects.filter(
            organization=account_request.contact,
            role=OrganizationRole.SHIPPER,
        ).first()
        self.assertIsNotNone(assignment)
        self.assertTrue(assignment.is_active)
