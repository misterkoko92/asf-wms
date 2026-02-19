from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contacts.models import Contact, ContactAddress, ContactType
from wms.models import AssociationProfile, AssociationRecipient, Destination
from wms.portal_permissions import ASSOCIATION_PORTAL_GROUP_NAME


class AuditAssociationProfilesCommandTests(TestCase):
    def _create_destination(self):
        correspondent = Contact.objects.create(
            name="Correspondant Audit",
            contact_type=ContactType.PERSON,
            is_active=True,
        )
        return Destination.objects.create(
            city="Paris",
            iata_code="AUD",
            country="France",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_profile(self, *, username="portal-audit", user_email="portal@example.com"):
        user = get_user_model().objects.create_user(
            username=username,
            email=user_email,
            password="pass1234",
        )
        contact = Contact.objects.create(
            name=f"Association {username}",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
            email=user_email,
        )
        ContactAddress.objects.create(
            contact=contact,
            address_line1="1 Rue Audit",
            city="Paris",
            country="France",
            is_default=True,
        )
        profile = AssociationProfile.objects.create(user=user, contact=contact)
        return profile

    def test_command_reports_success_when_no_issue(self):
        profile = self._create_profile()
        destination = self._create_destination()
        AssociationRecipient.objects.create(
            association_contact=profile.contact,
            destination=destination,
            name="Destinataire Audit",
            structure_name="Destinataire Audit",
            address_line1="2 Rue Audit",
            city="Paris",
            country="France",
            is_delivery_contact=True,
            is_active=True,
        )
        output = StringIO()

        call_command("audit_association_profiles", stdout=output)

        text = output.getvalue()
        self.assertIn("Aucune anomalie détectée.", text)

    def test_command_detects_issues_and_can_fail(self):
        profile = self._create_profile(username="portal-audit-issue")
        group = Group.objects.get(name=ASSOCIATION_PORTAL_GROUP_NAME)
        profile.user.groups.remove(group)
        profile.user.is_active = False
        profile.user.save(update_fields=["is_active"])
        output = StringIO()

        call_command("audit_association_profiles", stdout=output)
        text = output.getvalue()
        self.assertIn("anomalie(s) détectée(s)", text)
        self.assertIn("groupe Association_Portail manquant", text)
        self.assertIn("utilisateur inactif", text)

        with self.assertRaises(CommandError):
            call_command(
                "audit_association_profiles",
                "--fail-on-issues",
                stdout=StringIO(),
            )
