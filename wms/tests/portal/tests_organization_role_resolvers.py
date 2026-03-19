from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from contacts.models import Contact, ContactType
from wms.models import (
    Destination,
    OrganizationRole,
    OrganizationRoleAssignment,
    RecipientBinding,
    ShipperScope,
)
from wms.organization_role_resolvers import (
    MESSAGE_DESTINATION_REQUIRED,
    MESSAGE_RECIPIENT_BINDING_MISSING,
    MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED,
    MESSAGE_RECIPIENT_REQUIRED,
    MESSAGE_RECIPIENT_REVIEW_PENDING,
    MESSAGE_SHIPPER_COMPLIANCE_REQUIRED,
    MESSAGE_SHIPPER_OUT_OF_SCOPE,
    MESSAGE_SHIPPER_REQUIRED,
    MESSAGE_SHIPPER_REVIEW_PENDING,
    OrganizationRoleResolutionError,
    eligible_recipients_for_shipper_destination,
    eligible_shippers_for_destination,
    resolve_recipient_binding_for_operation,
    resolve_shipper_for_operation,
)


class OrganizationRoleResolversTests(TestCase):
    def _create_org(self, name: str) -> Contact:
        return Contact.objects.create(
            name=name,
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )

    def _create_destination(self, iata: str) -> Destination:
        correspondent = self._create_org(f"Correspondent {iata}")
        return Destination.objects.create(
            city=f"City {iata}",
            iata_code=iata,
            country="Country",
            correspondent_contact=correspondent,
            is_active=True,
        )

    def _create_shipper_assignment(
        self,
        shipper_org: Contact,
        *,
        is_active: bool = True,
    ) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=shipper_org,
            role=OrganizationRole.SHIPPER,
            is_active=is_active,
        )

    def _create_recipient_assignment(
        self,
        recipient_org: Contact,
        *,
        is_active: bool = True,
    ) -> OrganizationRoleAssignment:
        return OrganizationRoleAssignment.objects.create(
            organization=recipient_org,
            role=OrganizationRole.RECIPIENT,
            is_active=is_active,
        )

    def test_eligible_shippers_returns_empty_without_destination(self):
        self.assertFalse(eligible_shippers_for_destination(None).exists())

    def test_eligible_shippers_filters_scope_activity_and_window(self):
        destination = self._create_destination("BKO")
        other_destination = self._create_destination("CMN")

        shipper_in_scope = self._create_org("Shipper In Scope")
        shipper_global = self._create_org("Shipper Global")
        shipper_out_scope = self._create_org("Shipper Out Scope")
        shipper_expired_scope = self._create_org("Shipper Expired Scope")
        shipper_inactive_assignment = self._create_org("Shipper Inactive Assignment")

        in_scope_assignment = self._create_shipper_assignment(shipper_in_scope)
        ShipperScope.objects.create(
            role_assignment=in_scope_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        global_assignment = self._create_shipper_assignment(shipper_global)
        ShipperScope.objects.create(
            role_assignment=global_assignment,
            destination=None,
            all_destinations=True,
            is_active=True,
        )

        out_scope_assignment = self._create_shipper_assignment(shipper_out_scope)
        ShipperScope.objects.create(
            role_assignment=out_scope_assignment,
            destination=other_destination,
            all_destinations=False,
            is_active=True,
        )

        expired_scope_assignment = self._create_shipper_assignment(shipper_expired_scope)
        ShipperScope.objects.create(
            role_assignment=expired_scope_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
            valid_from=timezone.now() - timedelta(days=2),
            valid_to=timezone.now() - timedelta(days=1),
        )

        inactive_assignment = self._create_shipper_assignment(
            shipper_inactive_assignment,
            is_active=False,
        )
        ShipperScope.objects.create(
            role_assignment=inactive_assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        shipper_ids = set(
            eligible_shippers_for_destination(destination).values_list("id", flat=True)
        )
        self.assertEqual(shipper_ids, {shipper_in_scope.id, shipper_global.id})

    def test_eligible_recipients_returns_empty_for_missing_inputs(self):
        shipper_org = self._create_org("Shipper Missing Input")
        destination = self._create_destination("LFW")
        self.assertFalse(
            eligible_recipients_for_shipper_destination(
                shipper_org=None,
                destination=destination,
            ).exists()
        )
        self.assertFalse(
            eligible_recipients_for_shipper_destination(
                shipper_org=shipper_org,
                destination=None,
            ).exists()
        )

    def test_eligible_recipients_filters_binding_activity_and_window(self):
        shipper_org = self._create_org("Shipper Recipient Scope")
        destination = self._create_destination("NBO")

        recipient_allowed = self._create_org("Recipient Allowed")
        recipient_inactive_binding = self._create_org("Recipient Inactive Binding")
        recipient_expired_binding = self._create_org("Recipient Expired Binding")

        self._create_recipient_assignment(recipient_allowed, is_active=True)
        self._create_recipient_assignment(recipient_inactive_binding, is_active=True)
        self._create_recipient_assignment(recipient_expired_binding, is_active=True)

        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_allowed,
            destination=destination,
            is_active=True,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_inactive_binding,
            destination=destination,
            is_active=False,
        )
        RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_expired_binding,
            destination=destination,
            is_active=True,
            valid_from=timezone.now() - timedelta(days=2),
            valid_to=timezone.now() - timedelta(days=1),
        )

        recipient_ids = set(
            eligible_recipients_for_shipper_destination(
                shipper_org=shipper_org,
                destination=destination,
            ).values_list("id", flat=True)
        )
        self.assertEqual(recipient_ids, {recipient_allowed.id})

    def test_resolve_shipper_validates_required_inputs(self):
        shipper_org = self._create_org("Shipper Missing Inputs")
        destination = self._create_destination("BZV")

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_DESTINATION_REQUIRED,
        ):
            resolve_shipper_for_operation(shipper_org=shipper_org, destination=None)

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_REQUIRED,
        ):
            resolve_shipper_for_operation(shipper_org=None, destination=destination)

    def test_resolve_shipper_rejects_missing_or_inactive_assignment(self):
        shipper_org = self._create_org("Shipper Missing Assignment")
        destination = self._create_destination("CKY")

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_REVIEW_PENDING,
        ):
            resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)

        self._create_shipper_assignment(shipper_org, is_active=False)
        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_REVIEW_PENDING,
        ):
            resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=False)
    def test_resolve_shipper_rejects_non_compliant_assignment(self, _allowed_mock):
        shipper_org = self._create_org("Shipper Non Compliant")
        destination = self._create_destination("ACC")
        assignment = self._create_shipper_assignment(shipper_org, is_active=True)
        ShipperScope.objects.create(
            role_assignment=assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_COMPLIANCE_REQUIRED,
        ):
            resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=True)
    def test_resolve_shipper_rejects_out_of_scope_assignment(self, _allowed_mock):
        shipper_org = self._create_org("Shipper Out Of Scope")
        destination = self._create_destination("OUA")
        other_destination = self._create_destination("GOM")
        assignment = self._create_shipper_assignment(shipper_org, is_active=True)
        ShipperScope.objects.create(
            role_assignment=assignment,
            destination=other_destination,
            all_destinations=False,
            is_active=True,
        )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_OUT_OF_SCOPE,
        ):
            resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=True)
    def test_resolve_shipper_returns_assignment_when_valid(self, _allowed_mock):
        shipper_org = self._create_org("Shipper Valid")
        destination = self._create_destination("FIH")
        assignment = self._create_shipper_assignment(shipper_org, is_active=True)
        ShipperScope.objects.create(
            role_assignment=assignment,
            destination=destination,
            all_destinations=False,
            is_active=True,
        )

        resolved = resolve_shipper_for_operation(
            shipper_org=shipper_org,
            destination=destination,
        )
        self.assertEqual(resolved.pk, assignment.pk)

    def test_resolve_recipient_binding_validates_required_inputs(self):
        shipper_org = self._create_org("Shipper Recipient Inputs")
        recipient_org = self._create_org("Recipient Missing Inputs")
        destination = self._create_destination("LFW")

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_DESTINATION_REQUIRED,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=None,
            )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_REQUIRED,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=None,
                destination=destination,
            )

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_SHIPPER_REQUIRED,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=None,
                recipient_org=recipient_org,
                destination=destination,
            )

    def test_resolve_recipient_binding_rejects_missing_or_inactive_assignment(
        self,
    ):
        shipper_org = self._create_org("Shipper Recipient Review")
        recipient_org = self._create_org("Recipient Review")
        destination = self._create_destination("LUN")

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_REVIEW_PENDING,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )

        self._create_recipient_assignment(recipient_org, is_active=False)
        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_REVIEW_PENDING,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=False)
    def test_resolve_recipient_binding_rejects_non_compliant_assignment(
        self,
        _allowed_mock,
    ):
        shipper_org = self._create_org("Shipper Recipient Compliance")
        recipient_org = self._create_org("Recipient Non Compliant")
        destination = self._create_destination("NIM")
        self._create_recipient_assignment(recipient_org, is_active=True)

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=True)
    def test_resolve_recipient_binding_rejects_missing_binding(
        self,
        _allowed_mock,
    ):
        shipper_org = self._create_org("Shipper Recipient Missing Binding")
        recipient_org = self._create_org("Recipient Missing Binding")
        destination = self._create_destination("ROB")
        self._create_recipient_assignment(recipient_org, is_active=True)

        with self.assertRaisesMessage(
            OrganizationRoleResolutionError,
            MESSAGE_RECIPIENT_BINDING_MISSING,
        ):
            resolve_recipient_binding_for_operation(
                shipper_org=shipper_org,
                recipient_org=recipient_org,
                destination=destination,
            )

    @mock.patch("wms.organization_role_resolvers.is_role_operation_allowed", return_value=True)
    def test_resolve_recipient_binding_returns_binding_when_valid(
        self,
        _allowed_mock,
    ):
        shipper_org = self._create_org("Shipper Recipient Valid")
        recipient_org = self._create_org("Recipient Valid")
        destination = self._create_destination("KGL")
        self._create_recipient_assignment(recipient_org, is_active=True)
        binding = RecipientBinding.objects.create(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
            is_active=True,
        )

        resolved = resolve_recipient_binding_for_operation(
            shipper_org=shipper_org,
            recipient_org=recipient_org,
            destination=destination,
        )
        self.assertEqual(resolved.pk, binding.pk)
