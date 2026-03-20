from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from contacts.correspondent_recipient_promotion import (
    SUPPORT_ORGANIZATION_NAME,
    correspondent_recipient_target_key,
    resolve_correspondent_recipient_organization,
)
from contacts.models import Contact, ContactType
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


def _current_window_q(prefix: str = ""):
    now = timezone.now()
    return Q(**{f"{prefix}valid_from__lte": now}) & (
        Q(**{f"{prefix}valid_to__isnull": True}) | Q(**{f"{prefix}valid_to__gt": now})
    )


def _set_if_changed(instance, field_name: str, value, updated_fields: list[str]) -> None:
    if getattr(instance, field_name) != value:
        setattr(instance, field_name, value)
        updated_fields.append(field_name)


class ShipmentPartyBackfillService:
    def __init__(self):
        self.summary = {
            "shippers_created": 0,
            "shippers_updated": 0,
            "recipient_organizations_created": 0,
            "recipient_organizations_updated": 0,
            "recipient_contacts_created": 0,
            "recipient_contacts_updated": 0,
            "links_created": 0,
            "links_updated": 0,
            "authorized_contacts_created": 0,
            "authorized_contacts_updated": 0,
            "correspondent_recipient_organizations_created": 0,
            "conflicting_recipient_targets": 0,
            "recipient_bindings_skipped": 0,
            "correspondent_destinations_skipped": 0,
        }
        self.conflict_details: list[str] = []
        self._shippers_by_org_id: dict[int, ShipmentShipper] = {}
        self._recipient_orgs_by_org_id: dict[int, ShipmentRecipientOrganization] = {}
        self._recipient_contacts_by_key: dict[tuple[int, int], ShipmentRecipientContact] = {}
        self._conflicting_recipient_org_ids: set[int] = set()
        self._conflicting_correspondent_destination_ids: set[int] = set()

    def run(self) -> dict[str, object]:
        self._collect_destination_conflicts()
        self._backfill_shippers()
        self._backfill_recipient_bindings()
        self._backfill_correspondents()
        return {**self.summary, "conflict_details": list(self.conflict_details)}

    def _active_shipper_assignments(self):
        assignment_ids = (
            ShipperScope.objects.filter(
                is_active=True,
                role_assignment__role=OrganizationRole.SHIPPER,
                role_assignment__is_active=True,
                role_assignment__organization__is_active=True,
                role_assignment__organization__contact_type=ContactType.ORGANIZATION,
            )
            .filter(_current_window_q())
            .values_list("role_assignment_id", flat=True)
            .distinct()
        )
        return (
            OrganizationRoleAssignment.objects.filter(id__in=assignment_ids)
            .select_related("organization")
            .prefetch_related("role_contacts__contact", "shipper_scopes")
            .order_by("id")
        )

    def _active_shipper_assignment_for_org(self, organization: Contact):
        assignment_ids = (
            ShipperScope.objects.filter(
                is_active=True,
                role_assignment__organization=organization,
                role_assignment__role=OrganizationRole.SHIPPER,
                role_assignment__is_active=True,
                role_assignment__organization__is_active=True,
                role_assignment__organization__contact_type=ContactType.ORGANIZATION,
            )
            .filter(_current_window_q())
            .values_list("role_assignment_id", flat=True)
            .distinct()
        )
        return (
            OrganizationRoleAssignment.objects.filter(id__in=assignment_ids)
            .select_related("organization")
            .prefetch_related("role_contacts__contact", "shipper_scopes")
            .order_by("id")
            .first()
        )

    def _active_recipient_assignment_for_org(self, organization: Contact):
        return (
            OrganizationRoleAssignment.objects.filter(
                organization=organization,
                role=OrganizationRole.RECIPIENT,
                is_active=True,
                organization__is_active=True,
                organization__contact_type=ContactType.ORGANIZATION,
            )
            .prefetch_related("role_contacts__contact")
            .order_by("id")
            .first()
        )

    def _primary_legacy_role_contact(self, assignment: OrganizationRoleAssignment):
        return (
            assignment.role_contacts.select_related("contact")
            .filter(
                is_primary=True,
                is_active=True,
                contact__is_active=True,
            )
            .order_by("id")
            .first()
        )

    def _ensure_person_contact_from_legacy_contact(
        self,
        *,
        organization: Contact,
        legacy_contact,
    ) -> Contact | None:
        if legacy_contact is None or not legacy_contact.is_active:
            return None

        lookup = {
            "contact_type": ContactType.PERSON,
            "organization": organization,
            "first_name": legacy_contact.first_name,
            "last_name": legacy_contact.last_name,
            "email": legacy_contact.email,
        }
        person = Contact.objects.filter(**lookup).order_by("id").first()
        if person is None:
            return Contact.objects.create(
                name=" ".join(
                    part for part in [legacy_contact.first_name, legacy_contact.last_name] if part
                ).strip()
                or legacy_contact.email
                or f"Contact {organization.name}",
                contact_type=ContactType.PERSON,
                title=legacy_contact.title or "",
                first_name=legacy_contact.first_name,
                last_name=legacy_contact.last_name,
                organization=organization,
                email=legacy_contact.email,
                phone=legacy_contact.phone,
                is_active=legacy_contact.is_active,
            )

        updated_fields: list[str] = []
        _set_if_changed(person, "title", legacy_contact.title or "", updated_fields)
        _set_if_changed(person, "phone", legacy_contact.phone, updated_fields)
        _set_if_changed(person, "organization", organization, updated_fields)
        _set_if_changed(person, "is_active", legacy_contact.is_active, updated_fields)
        if updated_fields:
            person.save(update_fields=updated_fields)
        return person

    def _ensure_shipment_shipper_from_assignment(
        self,
        assignment: OrganizationRoleAssignment,
    ) -> ShipmentShipper | None:
        cached = self._shippers_by_org_id.get(assignment.organization_id)
        if cached is not None:
            return cached

        primary_link = self._primary_legacy_role_contact(assignment)
        if primary_link is None:
            return None

        default_contact = self._ensure_person_contact_from_legacy_contact(
            organization=assignment.organization,
            legacy_contact=primary_link.contact,
        )
        if default_contact is None:
            return None

        can_send_to_all = (
            assignment.shipper_scopes.filter(
                is_active=True,
                all_destinations=True,
            )
            .filter(_current_window_q())
            .exists()
        )

        shipper, created = ShipmentShipper.objects.get_or_create(
            organization=assignment.organization,
            defaults={
                "default_contact": default_contact,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "can_send_to_all": can_send_to_all,
                "is_active": True,
            },
        )
        if created:
            self.summary["shippers_created"] += 1
        else:
            updated_fields: list[str] = []
            _set_if_changed(shipper, "default_contact", default_contact, updated_fields)
            _set_if_changed(
                shipper,
                "validation_status",
                ShipmentValidationStatus.VALIDATED,
                updated_fields,
            )
            _set_if_changed(shipper, "can_send_to_all", can_send_to_all, updated_fields)
            _set_if_changed(shipper, "is_active", True, updated_fields)
            if updated_fields:
                shipper.save(update_fields=updated_fields)
                self.summary["shippers_updated"] += 1

        self._shippers_by_org_id[assignment.organization_id] = shipper
        return shipper

    def _ensure_shipment_shipper(self, organization: Contact) -> ShipmentShipper | None:
        cached = self._shippers_by_org_id.get(organization.id)
        if cached is not None:
            return cached

        assignment = self._active_shipper_assignment_for_org(organization)
        if assignment is None:
            return None
        return self._ensure_shipment_shipper_from_assignment(assignment)

    def _ensure_recipient_organization(
        self,
        *,
        organization: Contact,
        destination: Destination,
        is_correspondent: bool,
    ) -> ShipmentRecipientOrganization:
        cached = self._recipient_orgs_by_org_id.get(organization.id)
        if cached is not None:
            if cached.destination_id != destination.id:
                if cached.is_active:
                    raise CommandError(
                        f"Recipient organization {organization} is linked to multiple destinations "
                        f"({cached.destination} vs {destination})."
                    )
                updated_fields = ["destination"]
                cached.destination = destination
                _set_if_changed(
                    cached,
                    "validation_status",
                    ShipmentValidationStatus.VALIDATED,
                    updated_fields,
                )
                _set_if_changed(cached, "is_correspondent", is_correspondent, updated_fields)
                _set_if_changed(cached, "is_active", True, updated_fields)
                cached.save(update_fields=updated_fields)
                self.summary["recipient_organizations_updated"] += 1
                return cached
            if is_correspondent and not cached.is_correspondent:
                cached.is_correspondent = True
                cached.save(update_fields=["is_correspondent"])
                self.summary["recipient_organizations_updated"] += 1
            return cached

        recipient_organization, created = ShipmentRecipientOrganization.objects.get_or_create(
            organization=organization,
            defaults={
                "destination": destination,
                "validation_status": ShipmentValidationStatus.VALIDATED,
                "is_correspondent": is_correspondent,
                "is_active": True,
            },
        )
        if created:
            if is_correspondent:
                self.summary["correspondent_recipient_organizations_created"] += 1
            else:
                self.summary["recipient_organizations_created"] += 1
        else:
            updated_fields: list[str] = []
            if recipient_organization.destination_id != destination.id:
                if recipient_organization.is_active:
                    raise CommandError(
                        f"Recipient organization {organization} is linked to multiple destinations "
                        f"({recipient_organization.destination} vs {destination})."
                    )
                recipient_organization.destination = destination
                updated_fields.append("destination")
            _set_if_changed(
                recipient_organization,
                "validation_status",
                ShipmentValidationStatus.VALIDATED,
                updated_fields,
            )
            _set_if_changed(recipient_organization, "is_active", True, updated_fields)
            if is_correspondent:
                _set_if_changed(recipient_organization, "is_correspondent", True, updated_fields)
            if updated_fields:
                recipient_organization.save(update_fields=updated_fields)
                self.summary["recipient_organizations_updated"] += 1

        self._recipient_orgs_by_org_id[organization.id] = recipient_organization
        return recipient_organization

    def _ensure_recipient_contact(
        self,
        *,
        recipient_organization: ShipmentRecipientOrganization,
        contact: Contact,
        is_active: bool,
    ) -> ShipmentRecipientContact:
        cache_key = (recipient_organization.id, contact.id)
        cached = self._recipient_contacts_by_key.get(cache_key)
        if cached is not None:
            if cached.is_active != is_active:
                cached.is_active = is_active
                cached.save(update_fields=["is_active"])
                self.summary["recipient_contacts_updated"] += 1
            return cached

        recipient_contact, created = ShipmentRecipientContact.objects.get_or_create(
            recipient_organization=recipient_organization,
            contact=contact,
            defaults={"is_active": is_active},
        )
        if created:
            self.summary["recipient_contacts_created"] += 1
        else:
            if recipient_contact.is_active != is_active:
                recipient_contact.is_active = is_active
                recipient_contact.save(update_fields=["is_active"])
                self.summary["recipient_contacts_updated"] += 1

        self._recipient_contacts_by_key[cache_key] = recipient_contact
        return recipient_contact

    def _ensure_shipper_recipient_link(
        self,
        *,
        shipper: ShipmentShipper,
        recipient_organization: ShipmentRecipientOrganization,
    ) -> ShipmentShipperRecipientLink:
        link, created = ShipmentShipperRecipientLink.objects.get_or_create(
            shipper=shipper,
            recipient_organization=recipient_organization,
            defaults={"is_active": True},
        )
        if created:
            self.summary["links_created"] += 1
        else:
            if not link.is_active:
                link.is_active = True
                link.save(update_fields=["is_active"])
                self.summary["links_updated"] += 1
        return link

    def _ensure_authorized_recipient_contacts(
        self,
        *,
        link: ShipmentShipperRecipientLink,
        contacts: Iterable[ShipmentRecipientContact],
        default_contact: ShipmentRecipientContact | None,
    ) -> None:
        current_contact_ids = {contact.id for contact in contacts}
        stale_authorized = ShipmentAuthorizedRecipientContact.objects.filter(
            link=link,
            is_active=True,
        )
        if current_contact_ids:
            stale_authorized = stale_authorized.exclude(
                recipient_contact_id__in=current_contact_ids
            )
        deactivated = stale_authorized.update(is_active=False, is_default=False)
        if deactivated:
            self.summary["authorized_contacts_updated"] += deactivated

        default_contact_id = default_contact.id if default_contact else None
        if default_contact_id is None:
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_default=True,
            ).update(is_default=False)
        else:
            ShipmentAuthorizedRecipientContact.objects.filter(
                link=link,
                is_default=True,
            ).exclude(recipient_contact_id=default_contact_id).update(is_default=False)

        for shipment_contact in contacts:
            is_default = shipment_contact.id == default_contact_id
            authorized, created = ShipmentAuthorizedRecipientContact.objects.get_or_create(
                link=link,
                recipient_contact=shipment_contact,
                defaults={
                    "is_active": shipment_contact.is_active,
                    "is_default": is_default,
                },
            )
            if created:
                self.summary["authorized_contacts_created"] += 1
                continue

            updated_fields: list[str] = []
            _set_if_changed(authorized, "is_active", shipment_contact.is_active, updated_fields)
            _set_if_changed(authorized, "is_default", is_default, updated_fields)
            if updated_fields:
                authorized.save(update_fields=updated_fields)
                self.summary["authorized_contacts_updated"] += 1

    def _deactivate_stale_recipient_contacts(
        self,
        *,
        recipient_organization: ShipmentRecipientOrganization,
        active_contact_ids: set[int],
    ) -> None:
        stale_contacts = ShipmentRecipientContact.objects.filter(
            recipient_organization=recipient_organization,
            is_active=True,
        )
        if active_contact_ids:
            stale_contacts = stale_contacts.exclude(contact_id__in=active_contact_ids)
        deactivated = stale_contacts.update(is_active=False)
        if deactivated:
            self.summary["recipient_contacts_updated"] += deactivated

    def _recipient_contacts_from_assignment(
        self,
        *,
        recipient_organization: ShipmentRecipientOrganization,
        organization: Contact,
    ) -> tuple[list[ShipmentRecipientContact], ShipmentRecipientContact | None]:
        assignment = self._active_recipient_assignment_for_org(organization)
        if assignment is None:
            self._deactivate_stale_recipient_contacts(
                recipient_organization=recipient_organization,
                active_contact_ids=set(),
            )
            return [], None

        shipment_contacts: list[ShipmentRecipientContact] = []
        default_contact: ShipmentRecipientContact | None = None
        active_contact_ids: set[int] = set()

        for role_contact in (
            assignment.role_contacts.select_related("contact")
            .filter(
                is_active=True,
                contact__is_active=True,
            )
            .order_by("-is_primary", "id")
        ):
            person = self._ensure_person_contact_from_legacy_contact(
                organization=organization,
                legacy_contact=role_contact.contact,
            )
            if person is None:
                continue
            shipment_contact = self._ensure_recipient_contact(
                recipient_organization=recipient_organization,
                contact=person,
                is_active=True,
            )
            shipment_contacts.append(shipment_contact)
            active_contact_ids.add(person.id)
            if role_contact.is_primary and default_contact is None:
                default_contact = shipment_contact

        self._deactivate_stale_recipient_contacts(
            recipient_organization=recipient_organization,
            active_contact_ids=active_contact_ids,
        )
        if default_contact is None and shipment_contacts:
            default_contact = shipment_contacts[0]
        return shipment_contacts, default_contact

    def _backfill_shippers(self) -> None:
        for assignment in self._active_shipper_assignments():
            self._ensure_shipment_shipper_from_assignment(assignment)

    def _active_bindings(self):
        return (
            RecipientBinding.objects.filter(
                is_active=True,
                shipper_org__is_active=True,
                shipper_org__contact_type=ContactType.ORGANIZATION,
                recipient_org__is_active=True,
                recipient_org__contact_type=ContactType.ORGANIZATION,
                destination__is_active=True,
            )
            .filter(_current_window_q())
            .select_related("shipper_org", "recipient_org", "destination")
            .order_by("id")
        )

    def _collect_destination_conflicts(self) -> None:
        destinations_by_target: dict[tuple[str, object], set[str]] = defaultdict(set)
        labels_by_target: dict[tuple[str, object], str] = {}
        recipient_org_ids_by_target: dict[tuple[str, object], set[int]] = defaultdict(set)
        correspondent_destination_ids_by_target: dict[tuple[str, object], set[int]] = defaultdict(
            set
        )

        for shipment_recipient in ShipmentRecipientOrganization.objects.filter(
            is_active=True
        ).select_related(
            "organization",
            "destination",
        ):
            key = ("org", shipment_recipient.organization_id)
            destinations_by_target[key].add(str(shipment_recipient.destination))
            labels_by_target[key] = shipment_recipient.organization.name
            recipient_org_ids_by_target[key].add(shipment_recipient.organization_id)

        for binding in self._active_bindings():
            key = ("org", binding.recipient_org_id)
            destinations_by_target[key].add(str(binding.destination))
            labels_by_target[key] = binding.recipient_org.name
            recipient_org_ids_by_target[key].add(binding.recipient_org_id)

        for destination in Destination.objects.filter(is_active=True).select_related(
            "correspondent_contact",
            "correspondent_contact__organization",
        ):
            key, label = correspondent_recipient_target_key(destination.correspondent_contact)
            if key is None:
                continue
            destinations_by_target[key].add(str(destination))
            labels_by_target[key] = label
            correspondent_destination_ids_by_target[key].add(destination.id)

        for key, destinations in destinations_by_target.items():
            if len(destinations) <= 1:
                continue
            self._conflicting_recipient_org_ids.update(recipient_org_ids_by_target[key])
            self._conflicting_correspondent_destination_ids.update(
                correspondent_destination_ids_by_target[key]
            )
            detail_parts = []
            recipient_org_ids = sorted(recipient_org_ids_by_target[key])
            if recipient_org_ids:
                detail_parts.append(
                    "recipient_org_ids=" + ",".join(str(value) for value in recipient_org_ids)
                )
            correspondent_destination_ids = sorted(correspondent_destination_ids_by_target[key])
            if correspondent_destination_ids:
                detail_parts.append(
                    "destination_ids="
                    + ",".join(str(value) for value in correspondent_destination_ids)
                )
            detail_label = labels_by_target[key]
            detail_context = f" [{' ; '.join(detail_parts)}]" if detail_parts else ""
            self.conflict_details.append(
                f"{detail_label}{detail_context} -> {', '.join(sorted(destinations))}"
            )

        self.summary["conflicting_recipient_targets"] = len(self.conflict_details)

    def _backfill_recipient_bindings(self) -> None:
        for binding in self._active_bindings():
            if binding.recipient_org_id in self._conflicting_recipient_org_ids:
                self.summary["recipient_bindings_skipped"] += 1
                continue
            shipper = self._ensure_shipment_shipper(binding.shipper_org)
            if shipper is None:
                continue

            recipient_organization = self._ensure_recipient_organization(
                organization=binding.recipient_org,
                destination=binding.destination,
                is_correspondent=False,
            )
            shipment_contacts, default_contact = self._recipient_contacts_from_assignment(
                recipient_organization=recipient_organization,
                organization=binding.recipient_org,
            )
            link = self._ensure_shipper_recipient_link(
                shipper=shipper,
                recipient_organization=recipient_organization,
            )
            self._ensure_authorized_recipient_contacts(
                link=link,
                contacts=shipment_contacts,
                default_contact=default_contact,
            )

    def _backfill_correspondents(self) -> None:
        for destination in Destination.objects.filter(is_active=True).select_related(
            "correspondent_contact",
            "correspondent_contact__organization",
        ):
            if destination.id in self._conflicting_correspondent_destination_ids:
                self.summary["correspondent_destinations_skipped"] += 1
                continue
            resolution = resolve_correspondent_recipient_organization(
                destination.correspondent_contact
            )
            organization = resolution.organization
            if organization is None or not organization.is_active:
                continue

            existing_correspondent = (
                ShipmentRecipientOrganization.objects.filter(
                    destination=destination,
                    is_correspondent=True,
                )
                .order_by("-is_active", "id")
                .first()
            )
            if (
                existing_correspondent is not None
                and existing_correspondent.organization_id != organization.id
                and existing_correspondent.is_active
            ):
                existing_correspondent.is_active = False
                existing_correspondent.save(update_fields=["is_active"])
                self.summary["recipient_organizations_updated"] += 1

            recipient_organization = self._ensure_recipient_organization(
                organization=organization,
                destination=destination,
                is_correspondent=True,
            )

            correspondent_contact = destination.correspondent_contact
            if correspondent_contact.contact_type != ContactType.PERSON:
                continue
            self._ensure_recipient_contact(
                recipient_organization=recipient_organization,
                contact=correspondent_contact,
                is_active=correspondent_contact.is_active,
            )


def backfill_shipment_parties_from_org_roles(*, dry_run: bool) -> dict[str, object]:
    def _run() -> dict[str, object]:
        service = ShipmentPartyBackfillService()
        return service.run()

    with transaction.atomic():
        summary = _run()
        if dry_run:
            transaction.set_rollback(True)
        return summary


class Command(BaseCommand):
    help = "Backfill shipment-party structures from the legacy org-roles runtime."

    def add_arguments(self, parser):
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Execute the backfill without persisting changes.",
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Execute the backfill and persist changes.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        apply = bool(options.get("apply"))
        if dry_run and apply:
            raise CommandError("Choose either --dry-run or --apply, not both.")

        dry_run = not apply
        summary = backfill_shipment_parties_from_org_roles(dry_run=dry_run)
        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(f"Backfill shipment parties from org roles [{mode}]")
        self.stdout.write(
            "\n".join(
                [
                    f"- Shippers created: {summary['shippers_created']}",
                    f"- Recipient organizations created: {summary['recipient_organizations_created']}",
                    f"- Recipient contacts created: {summary['recipient_contacts_created']}",
                    f"- Shipper recipient links created: {summary['links_created']}",
                    (
                        "- Authorized recipient contacts created: "
                        f"{summary['authorized_contacts_created']}"
                    ),
                    (
                        "- Correspondent recipient organizations created: "
                        f"{summary['correspondent_recipient_organizations_created']}"
                    ),
                    f"- Conflicting recipient targets: {summary['conflicting_recipient_targets']}",
                    f"- Recipient bindings skipped: {summary['recipient_bindings_skipped']}",
                    (
                        "- Correspondent destinations skipped: "
                        f"{summary['correspondent_destinations_skipped']}"
                    ),
                ]
            )
        )
        conflict_details = summary.get("conflict_details") or []
        if conflict_details:
            self.stdout.write("Conflicts skipped:")
            self.stdout.write("\n".join(f"- {detail}" for detail in conflict_details))
