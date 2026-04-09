from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms import models


class RecipientPortalAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            "admin-recipient-models",
            "admin-recipient-models@example.com",
            "pass1234",  # pragma: allowlist secret
        )
        self.portal_user = user_model.objects.create_user(
            "portal-recipient-models",
            "portal-recipient-models@example.com",
            "pass1234",  # pragma: allowlist secret
        )
        self.organization = Contact.objects.create(
            name="Hopital Admin",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.destination = models.Destination.objects.create(
            city="Dakar",
            iata_code="DKR",
            country="Senegal",
            correspondent_contact=self.organization,
            is_active=True,
        )
        self.referent = Contact.objects.create(
            name="Alice Admin",
            first_name="Alice",
            last_name="Admin",
            contact_type=ContactType.PERSON,
            organization=self.organization,
            is_active=True,
        )
        self.shipper = models.ShipmentShipper.objects.create(
            organization=self.organization,
            default_contact=self.referent,
            validation_status=models.ShipmentValidationStatus.VALIDATED,
            is_active=True,
        )
        self.recipient_organization = models.ShipmentRecipientOrganization.objects.create(
            organization=self.organization,
            destination=self.destination,
            validation_status=models.ShipmentValidationStatus.PENDING,
            is_active=True,
        )
        self.portal_grant = models.PortalAccessGrant.objects.create(
            user=self.portal_user,
            role=models.PortalAccessRole.RECIPIENT_ADMIN,
            recipient_organization=self.recipient_organization,
            created_by=self.superuser,
        )
        self.product = models.Product.objects.create(
            sku="ADMIN-RECIP-001",
            name="Kit Admin",
            qr_code_image="qr_codes/admin_recip_001.png",
        )
        self.preference = models.RecipientProductPreference.objects.create(
            recipient_organization=self.recipient_organization,
            product=self.product,
            status=models.RecipientProductPreferenceStatus.REQUESTED,
            quantity_target=3,
            period_unit=models.RecipientProductPreferencePeriodUnit.WEEK,
            source=models.RecipientProductPreferenceSource.SCAN_ADMIN,
            created_by=self.superuser,
            updated_by=self.superuser,
        )
        self.structure_document = models.RecipientStructureDocument.objects.create(
            contact=self.organization,
            doc_type=models.RecipientStructureDocumentType.REGISTRATION_PROOF,
            status=models.DocumentReviewStatus.PENDING,
            file="recipient_structure_documents/proof.pdf",
            uploaded_by=self.superuser,
        )
        self.association_contact = Contact.objects.create(
            name="Association Legacy",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        self.legacy_projection = models.AssociationRecipient.objects.create(
            association_contact=self.association_contact,
            synced_contact=self.organization,
            destination=self.destination,
            name="Hopital Legacy",
            structure_name="Hopital Legacy",
            contact_first_name="Alice",
            contact_last_name="Admin",
            emails="alice.admin@example.com",
            phones="+33123456789",
            address_line1="1 rue legacy",
            city="Dakar",
            country="Senegal",
            is_active=True,
        )

    def test_canonical_models_are_registered_in_admin(self):
        self.assertIn(models.PortalAccessGrant, admin.site._registry)
        self.assertIn(models.ShipmentRecipientOrganization, admin.site._registry)
        self.assertIn(models.RecipientProductPreference, admin.site._registry)
        self.assertIn(models.RecipientStructureDocument, admin.site._registry)

    def test_canonical_admin_changelists_are_accessible(self):
        self.client.force_login(self.superuser)

        grant_response = self.client.get(reverse("admin:wms_portalaccessgrant_changelist"))
        recipient_response = self.client.get(
            reverse("admin:wms_shipmentrecipientorganization_changelist")
        )
        preference_response = self.client.get(
            reverse("admin:wms_recipientproductpreference_changelist")
        )
        document_response = self.client.get(
            reverse("admin:wms_recipientstructuredocument_changelist")
        )

        self.assertEqual(grant_response.status_code, 200)
        self.assertContains(grant_response, self.portal_user.username)
        self.assertContains(grant_response, self.destination.city)

        self.assertEqual(recipient_response.status_code, 200)
        self.assertContains(recipient_response, self.organization.name)
        self.assertContains(recipient_response, self.destination.city)

        self.assertEqual(preference_response.status_code, 200)
        self.assertContains(preference_response, self.product.name)
        self.assertContains(preference_response, self.organization.name)

        self.assertEqual(document_response.status_code, 200)
        self.assertContains(document_response, self.organization.name)

    def test_association_recipient_admin_is_inspection_only(self):
        admin_obj = admin.site._registry[models.AssociationRecipient]
        request = self.factory.get("/admin/")
        request.user = self.superuser

        self.assertFalse(admin_obj.has_add_permission(request))
        self.assertFalse(admin_obj.has_change_permission(request, obj=self.legacy_projection))
        self.assertFalse(admin_obj.has_delete_permission(request, obj=self.legacy_projection))

    def test_existing_portal_access_grant_locks_scope_identity_fields(self):
        admin_obj = admin.site._registry[models.PortalAccessGrant]
        request = self.factory.get("/admin/")
        request.user = self.superuser

        readonly_fields = admin_obj.get_readonly_fields(request, obj=self.portal_grant)

        self.assertIn("user", readonly_fields)
        self.assertIn("role", readonly_fields)
        self.assertIn("shipper", readonly_fields)
        self.assertIn("recipient_organization", readonly_fields)
        self.assertIn("created_at", readonly_fields)

    def test_existing_recipient_organization_locks_identity_fields(self):
        admin_obj = admin.site._registry[models.ShipmentRecipientOrganization]
        request = self.factory.get("/admin/")
        request.user = self.superuser

        readonly_fields = admin_obj.get_readonly_fields(request, obj=self.recipient_organization)

        self.assertIn("organization", readonly_fields)
        self.assertIn("destination", readonly_fields)
        self.assertIn("active_recipient_contact_count", readonly_fields)
        self.assertIn("active_shipper_link_count", readonly_fields)
        self.assertIn("active_portal_grant_count", readonly_fields)

    def test_existing_recipient_product_preference_locks_target_identity_fields(self):
        admin_obj = admin.site._registry[models.RecipientProductPreference]
        request = self.factory.get("/admin/")
        request.user = self.superuser

        readonly_fields = admin_obj.get_readonly_fields(request, obj=self.preference)

        self.assertIn("recipient_organization", readonly_fields)
        self.assertIn("product", readonly_fields)
        self.assertIn("category", readonly_fields)
        self.assertIn("created_at", readonly_fields)
        self.assertIn("updated_at", readonly_fields)
