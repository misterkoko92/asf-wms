from __future__ import annotations

from copy import deepcopy

from wms.models import PreparationRunNeedSnapshot, RecurringPreparationNeed


def _build_snapshot_payload(*, recurring_need):
    return {
        "recurring_need_id": recurring_need.id,
        "copied_from": {
            "period_unit": recurring_need.period_unit,
            "target_equivalent_units": recurring_need.target_equivalent_units,
            "is_active": recurring_need.is_active,
        },
    }


def snapshot_active_recurring_needs(*, run):
    snapshots = []
    active_needs = (
        RecurringPreparationNeed.objects.filter(is_active=True)
        .select_related("shipper", "recipient_organization", "destination")
        .order_by("shipper_id", "recipient_organization_id", "destination_id", "id")
    )
    for recurring_need in active_needs:
        snapshot, _created = PreparationRunNeedSnapshot.objects.update_or_create(
            run=run,
            recurring_need=recurring_need,
            defaults={
                "shipper": recurring_need.shipper,
                "recipient_organization": recurring_need.recipient_organization,
                "destination": recurring_need.destination,
                "period_unit": recurring_need.period_unit,
                "target_equivalent_units": recurring_need.target_equivalent_units,
                "snapshot_payload": _build_snapshot_payload(recurring_need=recurring_need),
            },
        )
        snapshots.append(snapshot)
    return snapshots


def override_preparation_need_snapshot(
    snapshot,
    *,
    target_equivalent_units=None,
    period_unit=None,
):
    payload = deepcopy(snapshot.snapshot_payload or {})
    override_payload = deepcopy(payload.get("override") or {})
    update_fields = []

    if target_equivalent_units is not None:
        snapshot.target_equivalent_units = target_equivalent_units
        override_payload["target_equivalent_units"] = target_equivalent_units
        update_fields.append("target_equivalent_units")

    if period_unit is not None:
        snapshot.period_unit = period_unit
        override_payload["period_unit"] = period_unit
        update_fields.append("period_unit")

    if not override_payload:
        return snapshot

    payload["override"] = override_payload
    snapshot.snapshot_payload = payload
    update_fields.append("snapshot_payload")
    snapshot.save(update_fields=update_fields)
    return snapshot
