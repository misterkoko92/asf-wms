from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from contacts.models import ContactType
from wms.models import Destination, OrganizationRole, OrganizationRoleAssignment
from wms.organization_role_resolvers import (
    MESSAGE_RECIPIENT_BINDING_MISSING,
    MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED,
    MESSAGE_RECIPIENT_REVIEW_PENDING,
    MESSAGE_SHIPPER_COMPLIANCE_REQUIRED,
    MESSAGE_SHIPPER_OUT_OF_SCOPE,
    MESSAGE_SHIPPER_REVIEW_PENDING,
    OrganizationRoleResolutionError,
    resolve_recipient_binding_for_operation,
    resolve_shipper_for_operation,
)

STATUS_ACCEPTED = "accepted"
STATUS_REFUSED = "refused"
STAGE_NONE = ""
STAGE_SHIPPER = "shipper"
STAGE_RECIPIENT_BINDING = "recipient_binding"


def _reason_code_for_error(error_message: str, *, stage: str) -> str:
    mapping = {
        MESSAGE_SHIPPER_REVIEW_PENDING: "shipper_review_pending",
        MESSAGE_SHIPPER_COMPLIANCE_REQUIRED: "shipper_compliance_required",
        MESSAGE_SHIPPER_OUT_OF_SCOPE: "shipper_out_of_scope",
        MESSAGE_RECIPIENT_REVIEW_PENDING: "recipient_review_pending",
        MESSAGE_RECIPIENT_COMPLIANCE_REQUIRED: "recipient_compliance_required",
        MESSAGE_RECIPIENT_BINDING_MISSING: "recipient_binding_missing",
    }
    return mapping.get(error_message, f"{stage or 'unknown'}_resolution_error")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_output_path(raw_value: str) -> Path:
    path = Path(raw_value)
    if not path.is_absolute():
        path = _project_root() / path
    return path.resolve()


class Command(BaseCommand):
    help = (
        "Exporte la matrice complete des triples destination/expediteur/destinataire "
        "avec statut accepte/refuse et motif."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/audits/org_role_triples_audit.csv",
            help="Chemin du CSV de sortie (defaut: docs/audits/org_role_triples_audit.csv).",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Inclure destinations et role assignments inactifs.",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=20000,
            help="Afficher une progression tous les N triples traites (defaut: 20000).",
        )
        parser.add_argument(
            "--max-triples",
            type=int,
            default=0,
            help="Limiter le nombre de triples evalues (0 = sans limite).",
        )

    def handle(self, *args, **options):
        include_inactive = bool(options.get("include_inactive"))
        progress_every = max(1, int(options.get("progress_every") or 20000))
        max_triples = max(0, int(options.get("max_triples") or 0))
        output_path = _resolve_output_path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        destinations_qs = Destination.objects.all().only(
            "id",
            "city",
            "iata_code",
            "is_active",
        )
        shipper_assignments_qs = (
            OrganizationRoleAssignment.objects.filter(
                role=OrganizationRole.SHIPPER,
                organization__contact_type=ContactType.ORGANIZATION,
            )
            .select_related("organization")
            .only(
                "id",
                "is_active",
                "organization__id",
                "organization__name",
                "organization__is_active",
            )
            .order_by("organization__name", "id")
        )
        recipient_assignments_qs = (
            OrganizationRoleAssignment.objects.filter(
                role=OrganizationRole.RECIPIENT,
                organization__contact_type=ContactType.ORGANIZATION,
            )
            .select_related("organization")
            .only(
                "id",
                "is_active",
                "organization__id",
                "organization__name",
                "organization__is_active",
            )
            .order_by("organization__name", "id")
        )

        if not include_inactive:
            destinations_qs = destinations_qs.filter(is_active=True)
            shipper_assignments_qs = shipper_assignments_qs.filter(
                is_active=True,
                organization__is_active=True,
            )
            recipient_assignments_qs = recipient_assignments_qs.filter(
                is_active=True,
                organization__is_active=True,
            )

        destinations = list(destinations_qs)
        shipper_assignments = list(shipper_assignments_qs)
        recipient_assignments = list(recipient_assignments_qs)

        if not destinations:
            raise CommandError("Aucune destination candidate pour l'audit.")
        if not shipper_assignments:
            raise CommandError("Aucun role assignment expediteur candidat pour l'audit.")
        if not recipient_assignments:
            raise CommandError("Aucun role assignment destinataire candidat pour l'audit.")

        estimated_total = len(destinations) * len(shipper_assignments) * len(recipient_assignments)
        self.stdout.write(self.style.MIGRATE_HEADING("Audit triples org roles [APPLY]"))
        self.stdout.write(
            f"- Destinations: {len(destinations)} | "
            f"Shippers: {len(shipper_assignments)} | "
            f"Recipients: {len(recipient_assignments)}"
        )
        self.stdout.write(f"- Triples estimes: {estimated_total}")
        if max_triples:
            self.stdout.write(f"- Limite max-triples: {max_triples}")

        processed = 0
        accepted = 0
        refused = 0
        refused_by_stage = Counter()
        refused_by_reason = Counter()

        headers = [
            "destination_id",
            "destination_iata",
            "destination_city",
            "destination_is_active",
            "shipper_assignment_id",
            "shipper_org_id",
            "shipper_org_name",
            "shipper_assignment_is_active",
            "recipient_assignment_id",
            "recipient_org_id",
            "recipient_org_name",
            "recipient_assignment_is_active",
            "status",
            "failed_stage",
            "reason_code",
            "reason_message",
        ]

        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()

            for destination in destinations:
                if max_triples and processed >= max_triples:
                    break
                for shipper_assignment in shipper_assignments:
                    if max_triples and processed >= max_triples:
                        break
                    shipper_org = shipper_assignment.organization

                    shipper_error_message = ""
                    try:
                        resolve_shipper_for_operation(
                            shipper_org=shipper_org,
                            destination=destination,
                        )
                    except OrganizationRoleResolutionError as exc:
                        shipper_error_message = str(exc)

                    for recipient_assignment in recipient_assignments:
                        if max_triples and processed >= max_triples:
                            break
                        recipient_org = recipient_assignment.organization
                        processed += 1

                        status = STATUS_ACCEPTED
                        failed_stage = STAGE_NONE
                        reason_message = ""
                        reason_code = ""

                        if shipper_error_message:
                            status = STATUS_REFUSED
                            failed_stage = STAGE_SHIPPER
                            reason_message = shipper_error_message
                            reason_code = _reason_code_for_error(
                                shipper_error_message,
                                stage=failed_stage,
                            )
                        else:
                            try:
                                resolve_recipient_binding_for_operation(
                                    shipper_org=shipper_org,
                                    recipient_org=recipient_org,
                                    destination=destination,
                                )
                            except OrganizationRoleResolutionError as exc:
                                status = STATUS_REFUSED
                                failed_stage = STAGE_RECIPIENT_BINDING
                                reason_message = str(exc)
                                reason_code = _reason_code_for_error(
                                    reason_message,
                                    stage=failed_stage,
                                )

                        if status == STATUS_ACCEPTED:
                            accepted += 1
                        else:
                            refused += 1
                            refused_by_stage[failed_stage] += 1
                            refused_by_reason[reason_code] += 1

                        writer.writerow(
                            {
                                "destination_id": destination.id,
                                "destination_iata": destination.iata_code,
                                "destination_city": destination.city,
                                "destination_is_active": destination.is_active,
                                "shipper_assignment_id": shipper_assignment.id,
                                "shipper_org_id": shipper_org.id,
                                "shipper_org_name": shipper_org.name,
                                "shipper_assignment_is_active": shipper_assignment.is_active,
                                "recipient_assignment_id": recipient_assignment.id,
                                "recipient_org_id": recipient_org.id,
                                "recipient_org_name": recipient_org.name,
                                "recipient_assignment_is_active": recipient_assignment.is_active,
                                "status": status,
                                "failed_stage": failed_stage,
                                "reason_code": reason_code,
                                "reason_message": reason_message,
                            }
                        )

                        if processed % progress_every == 0:
                            self.stdout.write(
                                f"- Progression: {processed}/{estimated_total} triples traites..."
                            )

        self.stdout.write(f"- Triples traites: {processed}")
        self.stdout.write(f"- Acceptes: {accepted}")
        self.stdout.write(f"- Refuses: {refused}")

        if refused:
            self.stdout.write("- Refus par etape:")
            for stage, count in sorted(refused_by_stage.items()):
                self.stdout.write(f"  - {stage}: {count}")

            self.stdout.write("- Refus par motif:")
            for reason_code, count in refused_by_reason.most_common():
                self.stdout.write(f"  - {reason_code}: {count}")

        self.stdout.write(f"- CSV: {output_path}")
