from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from math import inf

from django.db import transaction
from django.utils import timezone

from wms.models import (
    Flight,
    FlightSourceBatch,
    FlightSourceBatchStatus,
    PreparationCartonProposal,
    PreparationDestinationRule,
    PreparationParameterSet,
    PreparationProposalSource,
    PreparationRunStatus,
    PreparationShipmentProposal,
    PreparationShipmentProposalStatus,
    PreparationShipperMode,
    PreparationShipperRule,
    Product,
    RecipientProductPreference,
)
from wms.planning.flight_providers import PlanningFlightProviderError
from wms.planning.flight_sources import import_api_flights
from wms.preparation.candidates import (
    build_asf_stock_carton_candidates,
    build_deposited_carton_candidates,
)
from wms.preparation.needs import snapshot_active_recurring_needs
from wms.preparation.reservations import reserve_stock_for_carton_proposal
from wms.preparation.scoring import score_preparation_candidate


def _category_is_within(*, product_category, target_category):
    current = product_category
    while current is not None:
        if current.id == target_category.id:
            return True
        current = current.parent
    return False


def _products_from_preferences(*, recipient_organization):
    preferences = list(
        RecipientProductPreference.objects.filter(
            recipient_organization=recipient_organization,
            status__in=["requested", "allowed"],
        )
        .select_related("product", "category")
        .order_by("id")
    )
    products_by_id = {}
    if not preferences:
        return []

    exact_products = [preference.product for preference in preferences if preference.product_id]
    for product in exact_products:
        products_by_id[product.id] = product

    category_preferences = [preference for preference in preferences if preference.category_id]
    if category_preferences:
        stocked_products = (
            Product.objects.filter(productlot__status__isnull=False)
            .select_related("category__parent")
            .distinct()
            .order_by("id")
        )
        for product in stocked_products:
            category = getattr(product, "category", None)
            if category is None:
                continue
            for preference in category_preferences:
                if _category_is_within(
                    product_category=category, target_category=preference.category
                ):
                    products_by_id.setdefault(product.id, product)
                    break
    return list(products_by_id.values())


def _resolve_flight_batch(*, run, api_batch_loader=None):
    loader = api_batch_loader or import_api_flights
    try:
        batch = loader(
            start_date=run.flight_window_start,
            end_date=run.flight_window_end,
        )
        return batch, {
            "mode": getattr(batch, "source", "api"),
            "batch_id": batch.id,
            "used_fallback": False,
            "fallback_reason": "",
            "freshness_days": max(0, (run.flight_window_start - batch.imported_at.date()).days),
            "capacity_reference": "requested_window",
        }
    except PlanningFlightProviderError as exc:
        imported_batches = FlightSourceBatch.objects.filter(
            status=FlightSourceBatchStatus.IMPORTED,
            flights__isnull=False,
        ).distinct()
        fallback_batch = (
            imported_batches.filter(
                flights__departure_date__gte=run.flight_window_start,
                flights__departure_date__lte=run.flight_window_end,
            )
            .order_by("-imported_at", "-id")
            .first()
        )
        capacity_reference = "requested_window"
        if fallback_batch is None:
            fallback_batch = (
                imported_batches.filter(
                    period_end__isnull=False,
                    period_end__lt=run.flight_window_start,
                )
                .order_by("-period_end", "-imported_at", "-id")
                .first()
            )
            capacity_reference = "fallback_batch_period"
        if fallback_batch is None:
            fallback_batch = imported_batches.order_by("-imported_at", "-id").first()
            capacity_reference = "fallback_batch_period"
        if fallback_batch is None:
            raise
        return fallback_batch, {
            "mode": "fallback",
            "batch_id": fallback_batch.id,
            "used_fallback": True,
            "fallback_reason": str(exc),
            "freshness_days": max(
                0,
                (run.flight_window_start - fallback_batch.imported_at.date()).days,
            ),
            "capacity_reference": capacity_reference,
        }


def _destination_capacity(
    *, run, destination, destination_rule, flight_batch, use_batch_period=False
):
    flight_filters = {
        "batch": flight_batch,
        "destination": destination,
    }
    if not use_batch_period:
        flight_filters["departure_date__gte"] = run.flight_window_start
        flight_filters["departure_date__lte"] = run.flight_window_end
    flights = Flight.objects.filter(**flight_filters).order_by(
        "departure_date", "departure_time", "id"
    )
    if destination_rule.allowed_weekdays:
        allowed_weekdays = {str(day).lower() for day in destination_rule.allowed_weekdays}
        weekday_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        flights = [
            flight
            for flight in flights
            if weekday_names[flight.departure_date.weekday()] in allowed_weekdays
        ]
    else:
        flights = list(flights)

    usable_flights = flights
    if destination_rule.max_usable_flights_per_week:
        usable_flights = usable_flights[: destination_rule.max_usable_flights_per_week]

    per_flight_cap = destination_rule.max_equivalent_units_per_flight or inf
    capacity_units = 0
    for flight in usable_flights:
        flight_capacity = (
            flight.capacity_units if flight.capacity_units is not None else per_flight_cap
        )
        capacity_units += int(min(per_flight_cap, flight_capacity))

    if destination_rule.max_equivalent_units_per_week is not None:
        capacity_units = min(capacity_units, destination_rule.max_equivalent_units_per_week)

    shipment_limit = destination_rule.max_shipments_per_week
    if shipment_limit is None:
        shipment_limit = 10**9

    return {
        "capacity_units": max(0, int(capacity_units)),
        "usable_flight_count": len(usable_flights),
        "shipment_limit": int(shipment_limit),
    }


def _build_scope_specs(
    *,
    run,
    need_snapshot,
    shipper_rule,
    asf_shipper,
    include_unspecified,
    manual_reserve_quantities,
):
    deposited_candidates = build_deposited_carton_candidates(
        shipper=need_snapshot.shipper,
        recipient_organization=need_snapshot.recipient_organization,
        destination=need_snapshot.destination,
    )

    specs = []

    for candidate in deposited_candidates:
        best_score = None
        best_product = None
        for row in candidate.products:
            score_result = score_preparation_candidate(
                shipper=need_snapshot.shipper,
                recipient_organization=need_snapshot.recipient_organization,
                destination=need_snapshot.destination,
                product=row["product"],
                asf_shipper=asf_shipper,
                asf_penalty=1.0,
                shipper_score_coefficient=shipper_rule.score_coefficient,
                include_unspecified=include_unspecified,
            )
            if score_result.excluded:
                continue
            if best_score is None or score_result.score > best_score.score:
                best_score = score_result
                best_product = row["product"]
        if best_score is None:
            continue
        specs.append(
            {
                "source": PreparationProposalSource.DEPOSIT,
                "quantity": int(candidate.quantity),
                "product": best_product,
                "score": float(best_score.score),
                "score_result": best_score,
                "source_carton_id": candidate.carton.id if candidate.carton else None,
                "source_shipment_id": candidate.shipment.id if candidate.shipment else None,
                "reserve_quantity": False,
            }
        )

    if shipper_rule.mode in {
        PreparationShipperMode.ASF_COMPLEMENT_ALLOWED,
        PreparationShipperMode.ASF_AUTO_ALLOWED,
    }:
        for product in _products_from_preferences(
            recipient_organization=need_snapshot.recipient_organization
        ):
            stock_candidates = build_asf_stock_carton_candidates(
                product=product,
                manual_reserve_quantity=manual_reserve_quantities.get(product.id, 0),
            )
            if not stock_candidates:
                continue
            score_result = score_preparation_candidate(
                shipper=need_snapshot.shipper,
                recipient_organization=need_snapshot.recipient_organization,
                destination=need_snapshot.destination,
                product=product,
                asf_shipper=asf_shipper,
                asf_penalty=1.0,
                shipper_score_coefficient=shipper_rule.score_coefficient,
                include_unspecified=include_unspecified,
            )
            if score_result.excluded or score_result.remaining_need <= 0:
                continue
            specs.append(
                {
                    "source": PreparationProposalSource.ASF_STOCK,
                    "quantity": min(stock_candidates[0].quantity, score_result.remaining_need),
                    "product": product,
                    "score": float(score_result.score),
                    "score_result": score_result,
                    "source_carton_id": None,
                    "source_shipment_id": None,
                    "reserve_quantity": True,
                }
            )

    return sorted(
        specs,
        key=lambda spec: (
            -spec["score"],
            0 if asf_shipper is None or need_snapshot.shipper_id != asf_shipper.id else 1,
            -spec["score_result"].remaining_need,
            spec["product"].id if spec["product"] is not None else 0,
        ),
    )


def _shipment_source(chunk_rows):
    sources = {row["source"] for row in chunk_rows}
    if sources == {PreparationProposalSource.DEPOSIT}:
        return PreparationProposalSource.DEPOSIT
    if sources == {PreparationProposalSource.ASF_STOCK}:
        return PreparationProposalSource.ASF_STOCK
    return PreparationProposalSource.MIXED


def _create_shipment_proposal(
    *,
    run,
    need_snapshot,
    sequence,
    chunk_rows,
    created_by,
    manual_reserve_quantities,
):
    merged_rows = {}
    for row in chunk_rows:
        key = (
            row["source"],
            row["product"].id if row["product"] is not None else None,
            row["source_carton_id"],
            row["source_shipment_id"],
        )
        existing = merged_rows.get(key)
        if existing is None:
            merged_rows[key] = dict(row)
            continue
        existing["quantity"] += row["quantity"]
        existing["score"] += row["score"]

    chunk_rows = list(merged_rows.values())
    shipment_proposal = PreparationShipmentProposal.objects.create(
        run=run,
        shipper=need_snapshot.shipper,
        recipient_organization=need_snapshot.recipient_organization,
        destination=need_snapshot.destination,
        sequence=sequence,
        source=_shipment_source(chunk_rows),
        status=PreparationShipmentProposalStatus.PROPOSED,
        equivalent_units_total=sum(row["quantity"] for row in chunk_rows),
        score=Decimal(str(sum(row["score"] for row in chunk_rows))),
        rationale={
            "reasons": [reason for row in chunk_rows for reason in row["score_result"].reasons],
        },
    )
    for row in chunk_rows:
        carton_proposal = PreparationCartonProposal.objects.create(
            shipment_proposal=shipment_proposal,
            product=row["product"],
            source=row["source"],
            status=PreparationShipmentProposalStatus.PROPOSED,
            quantity=row["quantity"],
            equivalent_units_total=row["quantity"],
            rationale={
                "score_reasons": row["score_result"].reasons,
                "source_carton_id": row["source_carton_id"],
                "source_shipment_id": row["source_shipment_id"],
            },
        )
        if row["reserve_quantity"]:
            reserve_stock_for_carton_proposal(
                run=run,
                shipment_proposal=shipment_proposal,
                carton_proposal=carton_proposal,
                created_by=created_by,
                manual_reserve_quantity=manual_reserve_quantities.get(row["product"].id, 0),
            )
    return shipment_proposal


@transaction.atomic
def generate_preparation_run(
    *,
    run,
    shippers,
    destinations,
    api_batch_loader=None,
    asf_shipper=None,
    include_unspecified=False,
    manual_reserve_quantities=None,
):
    manual_reserve_quantities = manual_reserve_quantities or {}
    shippers = list(shippers)
    destinations = list(destinations)
    shipper_ids = {shipper.id for shipper in shippers}
    destination_ids = {destination.id for destination in destinations}

    need_snapshots = [
        snapshot
        for snapshot in snapshot_active_recurring_needs(run=run)
        if snapshot.shipper_id in shipper_ids and snapshot.destination_id in destination_ids
    ]

    flight_batch, flight_source = _resolve_flight_batch(
        run=run,
        api_batch_loader=api_batch_loader,
    )

    shipper_rules = {
        rule.shipper_id: rule
        for rule in PreparationShipperRule.objects.filter(
            parameter_set=run.parameter_set,
            shipper_id__in=shipper_ids,
            is_active=True,
        )
    }
    destination_rules = {
        rule.destination_id: rule
        for rule in PreparationDestinationRule.objects.filter(
            parameter_set=run.parameter_set,
            destination_id__in=destination_ids,
            is_active=True,
        )
    }

    destination_capacity = {}
    use_batch_period = flight_source.get("capacity_reference") == "fallback_batch_period"
    for destination in destinations:
        rule = destination_rules.get(destination.id)
        if rule is None:
            continue
        destination_capacity[destination.id] = _destination_capacity(
            run=run,
            destination=destination,
            destination_rule=rule,
            flight_batch=flight_batch,
            use_batch_period=use_batch_period,
        )

    run.parameter_snapshot = {
        "inputs": {
            "shipper_ids": [shipper.id for shipper in shippers],
            "destination_ids": [destination.id for destination in destinations],
            "target_equivalent_units": run.target_equivalent_units,
            "target_shipment_count": run.target_shipment_count,
            "target_shipment_size_units": run.target_shipment_size_units,
            "min_shipment_size_units": run.min_shipment_size_units,
            "max_shipment_size_units": run.max_shipment_size_units,
        },
        "flight_source": flight_source,
        "backlog": [],
    }

    total_remaining_units = int(run.target_equivalent_units)
    total_remaining_shipments = int(run.target_shipment_count)
    max_size_units = run.max_shipment_size_units or run.target_shipment_size_units
    sequence_by_scope = defaultdict(int)

    for need_snapshot in need_snapshots:
        if total_remaining_units <= 0 or total_remaining_shipments <= 0:
            break

        shipper_rule = shipper_rules.get(need_snapshot.shipper_id)
        capacity = destination_capacity.get(need_snapshot.destination_id)
        if shipper_rule is None or capacity is None:
            continue
        if capacity["capacity_units"] <= 0 or capacity["shipment_limit"] <= 0:
            continue

        scope_limit = min(
            int(need_snapshot.target_equivalent_units),
            total_remaining_units,
            capacity["capacity_units"],
        )
        if scope_limit <= 0:
            continue

        specs = _build_scope_specs(
            run=run,
            need_snapshot=need_snapshot,
            shipper_rule=shipper_rule,
            asf_shipper=asf_shipper,
            include_unspecified=include_unspecified,
            manual_reserve_quantities=manual_reserve_quantities,
        )
        if not specs:
            continue

        chunk_rows = []
        current_total = 0
        scope_remaining = scope_limit

        def finalize_or_backlog():
            nonlocal chunk_rows, current_total, total_remaining_units, total_remaining_shipments
            if not chunk_rows:
                return
            if current_total < run.min_shipment_size_units:
                run.parameter_snapshot["backlog"].append(
                    {
                        "shipper_id": need_snapshot.shipper_id,
                        "recipient_organization_id": need_snapshot.recipient_organization_id,
                        "destination_id": need_snapshot.destination_id,
                        "equivalent_units": current_total,
                        "reason": "below_min_shipment_size",
                    }
                )
            else:
                sequence_by_scope[
                    (
                        need_snapshot.shipper_id,
                        need_snapshot.recipient_organization_id,
                        need_snapshot.destination_id,
                    )
                ] += 1
                _create_shipment_proposal(
                    run=run,
                    need_snapshot=need_snapshot,
                    sequence=sequence_by_scope[
                        (
                            need_snapshot.shipper_id,
                            need_snapshot.recipient_organization_id,
                            need_snapshot.destination_id,
                        )
                    ],
                    chunk_rows=chunk_rows,
                    created_by=run.created_by,
                    manual_reserve_quantities=manual_reserve_quantities,
                )
                total_remaining_units -= current_total
                total_remaining_shipments -= 1
                capacity["shipment_limit"] -= 1
            chunk_rows = []
            current_total = 0

        for spec in specs:
            available = min(int(spec["quantity"]), scope_remaining)
            while (
                available > 0
                and scope_remaining > 0
                and total_remaining_shipments > 0
                and capacity["shipment_limit"] > 0
            ):
                if current_total >= max_size_units:
                    finalize_or_backlog()
                    if total_remaining_shipments <= 0 or capacity["shipment_limit"] <= 0:
                        break

                room = run.target_shipment_size_units - current_total
                if room <= 0:
                    room = max_size_units - current_total
                room = max(0, room)
                if room <= 0:
                    finalize_or_backlog()
                    continue

                take = min(available, scope_remaining, room)
                if take <= 0:
                    break
                chunk_rows.append(
                    {
                        **spec,
                        "quantity": take,
                    }
                )
                current_total += take
                available -= take
                scope_remaining -= take
                capacity["capacity_units"] -= take

            if total_remaining_shipments <= 0 or capacity["shipment_limit"] <= 0:
                break

        finalize_or_backlog()

    run.status = PreparationRunStatus.GENERATED
    run.save(update_fields=["parameter_snapshot", "status", "updated_at"])
    return run
