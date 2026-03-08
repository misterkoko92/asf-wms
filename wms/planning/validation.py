from wms.models import PlanningIssue, PlanningIssueSeverity


def get_destination_rule_map(run):
    if run.parameter_set_id is None:
        return {}
    return {
        rule.destination_id: rule
        for rule in run.parameter_set.destination_rules.filter(is_active=True).select_related(
            "destination"
        )
    }


def create_issue(
    *,
    run,
    code,
    message,
    source_model="",
    source_pk=None,
    severity=PlanningIssueSeverity.ERROR,
    context=None,
):
    return PlanningIssue.objects.create(
        run=run,
        severity=severity,
        code=code,
        message=message,
        source_model=source_model,
        source_pk=source_pk,
        context=context or {},
    )


def validate_run_inputs(*, run, shipments, destination_rule_map):
    if run.parameter_set_id is None:
        create_issue(
            run=run,
            code="missing_parameter_set",
            message="Le run de planning doit reference un jeu de parametres.",
            source_model="wms.PlanningRun",
            source_pk=run.pk,
        )

    for shipment in shipments:
        if shipment.destination_id is None:
            create_issue(
                run=run,
                code="missing_destination",
                message=f"L'expedition {shipment.reference} n'a pas de destination.",
                source_model="wms.Shipment",
                source_pk=shipment.pk,
            )
            continue
        if shipment.destination_id not in destination_rule_map:
            create_issue(
                run=run,
                code="missing_destination_rule",
                message=(
                    f"Aucune regle planning active pour la destination "
                    f"{shipment.destination.iata_code} de l'expedition {shipment.reference}."
                ),
                source_model="wms.Shipment",
                source_pk=shipment.pk,
                context={"destination_iata": shipment.destination.iata_code},
            )
