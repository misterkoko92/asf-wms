from django.core.management.base import BaseCommand

from wms.parties.rebuild import rebuild_recipient_party_graph


class Command(BaseCommand):
    help = "Rebuild recipient portal compatibility state from the canonical shipment-party graph."

    def add_arguments(self, parser):
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the rebuild without persisting changes.",
        )
        mode_group.add_argument(
            "--apply",
            action="store_true",
            help="Apply the rebuild to the database.",
        )

    def handle(self, *args, **options):
        apply = bool(options.get("apply"))
        summary = rebuild_recipient_party_graph(apply=apply)
        mode = summary["mode"]
        self.stdout.write(self.style.MIGRATE_HEADING(f"Recipient party graph rebuild [{mode}]"))
        self.stdout.write(
            "\n".join(
                [
                    (
                        "- Recipient organizations scanned: "
                        f"{summary['recipient_organizations_scanned']}"
                    ),
                    f"- Duplicate scopes: {len(summary['duplicate_scopes'])}",
                    (
                        "- Recipient organizations merged: "
                        f"{summary['recipient_organizations_merged']}"
                    ),
                    f"- Shipper grants created: {summary['shipper_grants_created']}",
                    ("- Recipient grants reassigned: " f"{summary['recipient_grants_reassigned']}"),
                    (
                        "- Legacy projections refreshed: "
                        f"{summary['legacy_projections_refreshed']}"
                    ),
                ]
            )
        )
        for scope in summary["duplicate_scopes"]:
            self.stdout.write(
                "  - Duplicate scope: "
                f"{scope['organization_name']} / {scope['destination_label']} "
                f"[{', '.join(str(pk) for pk in scope['recipient_organization_ids'])}]"
            )
