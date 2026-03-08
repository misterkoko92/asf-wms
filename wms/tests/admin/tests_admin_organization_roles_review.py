from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms import models
from wms.admin_organization_roles_review import (
    _collect_destination_ids_for_contact,
    _latest_recipient_binding,
    _resolve_recipient_organization,
    _suggest_destination_id,
    _suggest_shipper_id,
)
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

    def _activate_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

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

    @override_settings(WMS_ENABLE_RUNTIME_ENGLISH_TRANSLATION=False)
    def test_resolve_binding_success_message_renders_in_english(self):
        recipient_org = self._create_org("Recipient English")
        shipper_org = self._create_org("Shipper English")
        destination = self._create_destination("LFW")
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={"recipient_id": recipient_org.id},
        )

        self.client.force_login(self.superuser)
        self._activate_english()
        response = self.client.post(
            self.url,
            {
                "action": "resolve_binding",
                "item_id": str(review_item.id),
                "shipper_org_id": str(shipper_org.id),
                "destination_id": str(destination.id),
                "resolution_note": "English path",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recipient mapping saved and review item resolved.")
        self.assertNotContains(response, "Mapping destinataire valide et item resolu.")

    def test_resolve_recipient_organization_falls_back_to_legacy_contact_or_legacy_org(self):
        recipient_org = self._create_org("Recipient Legacy")
        legacy_person = Contact.objects.create(
            name="Legacy Person",
            contact_type=ContactType.PERSON,
            is_active=True,
            organization=recipient_org,
        )
        review_item_from_person = models.MigrationReviewItem.objects.create(
            organization=None,
            legacy_contact=legacy_person,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )
        self.assertEqual(
            _resolve_recipient_organization(review_item_from_person).id,
            recipient_org.id,
        )

        legacy_org = self._create_org("Legacy Organization")
        review_item_from_org = models.MigrationReviewItem.objects.create(
            organization=None,
            legacy_contact=legacy_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )
        self.assertEqual(
            _resolve_recipient_organization(review_item_from_org).id,
            legacy_org.id,
        )

    def test_resolve_recipient_organization_returns_none_without_legacy_contact(self):
        review_item = models.MigrationReviewItem.objects.create(
            organization=None,
            legacy_contact=None,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )

        self.assertIsNone(_resolve_recipient_organization(review_item))

    def test_collect_destination_ids_for_contact_includes_m2m_and_direct_destination(self):
        recipient_org = self._create_org("Recipient Destinations")
        destination_a = self._create_destination("BKO")
        destination_b = self._create_destination("ABJ")
        recipient_org.destination = destination_a
        recipient_org.save(update_fields=["destination"])
        recipient_org.destinations.add(destination_b)

        destination_ids = _collect_destination_ids_for_contact(recipient_org)

        self.assertEqual(destination_ids, {destination_a.id, destination_b.id})

    def test_suggest_shipper_and_destination_fallbacks_cover_history_and_single_option(self):
        recipient_org = self._create_org("Recipient Suggest Fallback")
        shipper_org = self._create_org("Shipper Suggest Fallback")
        destination = self._create_destination("NBO")
        recipient_org.linked_shippers.add(shipper_org)
        recipient_org.destination = destination
        recipient_org.save(update_fields=["destination"])
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
            payload={},
        )

        suggested_shipper_id = _suggest_shipper_id(
            review_item=review_item,
            recipient_org=recipient_org,
            shipper_options=[shipper_org],
        )
        suggested_destination_id = _suggest_destination_id(
            review_item=review_item,
            recipient_org=recipient_org,
            destination_options=[destination],
        )
        self.assertEqual(suggested_shipper_id, shipper_org.id)
        self.assertEqual(suggested_destination_id, destination.id)
        self.assertIsNotNone(_latest_recipient_binding(recipient_org))
        self.assertIsNone(_latest_recipient_binding(None))

    def test_resolve_binding_rejects_invalid_shipper_and_invalid_destination(self):
        recipient_org = self._create_org("Recipient Errors")
        shipper_org = self._create_org("Shipper Errors")
        destination = self._create_destination("CMN")
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_SHIPPER_LINKS,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )

        self.client.force_login(self.superuser)
        response_invalid_shipper = self.client.post(
            self.url,
            {
                "action": "resolve_binding",
                "item_id": str(review_item.id),
                "shipper_org_id": "999999",
                "destination_id": str(destination.id),
            },
            follow=False,
        )
        self.assertEqual(response_invalid_shipper.status_code, 302)
        self.assertEqual(
            models.RecipientBinding.objects.filter(recipient_org=recipient_org).count(),
            0,
        )

        response_invalid_destination = self.client.post(
            self.url,
            {
                "action": "resolve_binding",
                "item_id": str(review_item.id),
                "shipper_org_id": str(shipper_org.id),
                "destination_id": "999999",
            },
            follow=False,
        )
        self.assertEqual(response_invalid_destination.status_code, 302)
        self.assertEqual(
            models.RecipientBinding.objects.filter(recipient_org=recipient_org).count(),
            0,
        )

    def test_post_resolve_without_binding_closes_item(self):
        recipient_org = self._create_org("Recipient Close")
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_DESTINATION,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )

        self.client.force_login(self.superuser)
        response = self.client.post(
            self.url,
            {
                "action": "resolve_without_binding",
                "item_id": str(review_item.id),
                "resolution_note": "No binding needed",
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        review_item.refresh_from_db()
        self.assertEqual(review_item.status, models.MigrationReviewItemStatus.RESOLVED)
        self.assertEqual(review_item.resolved_by_id, self.superuser.id)
        self.assertEqual(review_item.resolution_note, "No binding needed")

    def test_post_with_missing_item_or_unknown_action_redirects(self):
        recipient_org = self._create_org("Recipient Unknown")
        review_item = models.MigrationReviewItem.objects.create(
            organization=recipient_org,
            role=models.OrganizationRole.RECIPIENT,
            reason_code=REVIEW_REASON_MISSING_DESTINATION,
            status=models.MigrationReviewItemStatus.OPEN,
            payload={},
        )
        self.client.force_login(self.superuser)

        missing_item_response = self.client.post(
            self.url,
            {"action": "resolve_binding", "item_id": "999999"},
            follow=False,
        )
        self.assertEqual(missing_item_response.status_code, 302)

        unknown_action_response = self.client.post(
            self.url,
            {"action": "unknown", "item_id": str(review_item.id)},
            follow=False,
        )
        self.assertEqual(unknown_action_response.status_code, 302)
