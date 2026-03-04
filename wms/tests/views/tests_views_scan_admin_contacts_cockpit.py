from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contacts.models import Contact, ContactType
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment, RecipientBinding


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
