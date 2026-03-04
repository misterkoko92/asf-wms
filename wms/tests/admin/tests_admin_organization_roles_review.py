from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms import models
from wms.organization_roles_backfill import (
    REVIEW_REASON_MISSING_DESTINATION,
    REVIEW_REASON_MISSING_SHIPPER_LINKS,
)


class OrganizationRolesReviewAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="org-review-admin",
            email="org-review-admin@example.org",
            password="pass1234",
        )
        self.staff_user = user_model.objects.create_user(
            username="org-review-staff",
            email="org-review-staff@example.org",
            password="pass1234",
            is_staff=True,
        )
        self.url = reverse("admin:wms_organization_roles_review")

    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> models.Destination:
        correspondent = self._create_org(f"Correspondent {iata}")
        return models.Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def test_requires_superuser_access(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_lists_only_open_review_items(self):
        recipient_org = self._create_org("Recipient Open")
        resolved_org = self._create_org("Recipient Resolved")

        models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={"recipient_id": recipient_org.id},
        )
        models.MigrationReviewItem.objects.create(
            organization=resolved_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_DESTINATION,
            status=models.MigrationReviewItemStatus.RESOLVED,
            payload={"recipient_id": resolved_org.id},
        )

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recipient Open")
        self.assertNotContains(response, "Recipient Resolved")

    def test_prefills_suggestions_from_matching_and_history(self):
        recipient_org = self._create_org("Recipient Suggest")
        shipper_org = self._create_org("Shipper Suggest")
        destination = self._create_destination("BKO")

        recipient_org.linked_shippers.add(shipper_org)
        recipient_org.destinations.add(destination)
        models.RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={"recipient_id": recipient_org.id},
        )

        self.client.force_login(self.superuser)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)
        row = next(
            item for item in response.context["review_items"] if item["item"].id == review_item.id
        )
        self.assertEqual(row["suggested_shipper_id"], shipper_org.id)
        self.assertEqual(row["suggested_destination_id"], destination.id)
        self.assertIn(
            shipper_org.id,
            [option.id for option in row["shipper_options"]],
        )
        self.assertIn(
            destination.id,
            [option.id for option in row["destination_options"]],
        )

    def test_manual_validation_creates_binding_and_resolves_review_item(self):
        recipient_org = self._create_org("Recipient Manual")
        shipper_org = self._create_org("Shipper Manual")
        destination = self._create_destination("DLA")
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={"recipient_id": recipient_org.id},
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            self.url,
            {
                "action": "resolve_binding",
                "item_id": str(review_item.id),
                "shipper_org_id": str(shipper_org.id),
                "destination_id": str(destination.id),
                "resolution_note": "Validation manuelle ASF",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            models.RecipientBinding.objects.filter(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
                is_active=True,
            ).exists()
        )

        review_item.refresh_from_db()
        self.assertEqual(review_item.status, models.MigrationReviewItemStatus.RESOLVED)
        self.assertEqual(review_item.resolved_by_id, self.superuser.id)
        self.assertIsNotNone(review_item.resolved_at)

        self.assertTrue(
            models.OrganizationRoleAssignment.objects.filter(
                organization=shipper_org,
                role=models.OrganizationRole.SHIPPER,
            ).exists()
        )
        self.assertTrue(
            models.OrganizationRoleAssignment.objects.filter(
                organization=recipient_org,
                role=models.OrganizationRole.RECIPIENT,
            ).exists()
        )
