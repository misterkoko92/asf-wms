import json
from dataclasses import dataclass
from pathlib import Path

from django.contrib.auth import get_user_model

from wms.models import (
    PlanningFlightSnapshot,
    PlanningRun,
    PlanningRunStatus,
    PlanningShipmentSnapshot,
    PlanningVolunteerSnapshot,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "solver_reference_cases"


@dataclass
class SolverReferenceCase:
    run: PlanningRun
    expected_assignments: list[tuple[str, str, str]]
    expected_result: dict


def load_reference_case(name: str) -> SolverReferenceCase:
    path = FIXTURE_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    planner = get_user_model().objects.create_user(
        username=f"reference-{name}@example.com",
        email=f"reference-{name}@example.com",
        password="pass1234",  # pragma: allowlist secret
    )
    run = PlanningRun.objects.create(
        week_start=data["week_start"],
        week_end=data["week_end"],
        status=PlanningRunStatus.READY,
        created_by=planner,
    )

    for shipment in data["shipments"]:
        PlanningShipmentSnapshot.objects.create(
            run=run,
            shipment_reference=shipment["reference"],
            shipper_name=shipment.get("shipper_name", "Reference shipper"),
            destination_iata=shipment["destination_iata"],
            priority=shipment.get("priority", 0),
            carton_count=shipment["carton_count"],
            equivalent_units=shipment["equivalent_units"],
            payload=shipment.get("payload", {}),
        )

    for volunteer in data["volunteers"]:
        PlanningVolunteerSnapshot.objects.create(
            run=run,
            volunteer_label=volunteer["label"],
            max_colis_vol=volunteer.get("max_colis_vol"),
            availability_summary=volunteer.get("availability_summary", {}),
            payload=volunteer.get("payload", {}),
        )

    for flight in data["flights"]:
        PlanningFlightSnapshot.objects.create(
            run=run,
            flight_number=flight["flight_number"],
            departure_date=flight["departure_date"],
            destination_iata=flight["destination_iata"],
            capacity_units=flight.get("capacity_units"),
            payload=flight.get("payload", {}),
        )

    return SolverReferenceCase(
        run=run,
        expected_assignments=[tuple(item) for item in data["expected_assignments"]],
        expected_result=data.get("expected_result", {}),
    )
