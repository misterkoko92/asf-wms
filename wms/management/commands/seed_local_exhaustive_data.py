from django.core.management.base import BaseCommand

from wms.local_exhaustive_seed import (
    render_local_exhaustive_seed_summary,
    seed_local_exhaustive_dataset,
)


class Command(BaseCommand):
    help = "Seed an exhaustive local-only recipe dataset for manual QA and end-to-end checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            default="local-exhaustive",
            help="Scenario slug used to namespace the local exhaustive dataset.",
        )
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Reset operational data before seeding the scenario.",
        )
        parser.add_argument(
            "--with-planning-solve",
            action="store_true",
            help="Solve the seeded planning run after creating the dataset.",
        )
        parser.add_argument(
            "--with-demo-documents",
            action="store_true",
            help="Attach representative uploaded documents to seeded flows.",
        )
        parser.add_argument(
            "--with-queue-backlog",
            action="store_true",
            help="Create representative email and document queue backlog rows.",
        )
        parser.add_argument(
            "--with-e2e-baseline",
            action="store_true",
            help="Seed extra records reserved for targeted local end-to-end checks.",
        )

    def handle(self, *args, **options):
        summary = seed_local_exhaustive_dataset(
            scenario_slug=options["scenario"],
            fresh=bool(options["fresh"]),
            with_planning_solve=bool(options["with_planning_solve"]),
            with_demo_documents=bool(options["with_demo_documents"]),
            with_queue_backlog=bool(options["with_queue_backlog"]),
            with_e2e_baseline=bool(options["with_e2e_baseline"]),
        )
        self.stdout.write(render_local_exhaustive_seed_summary(summary))
