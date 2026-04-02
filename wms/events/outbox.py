from __future__ import annotations

from wms.models import IntegrationDirection, IntegrationEvent, IntegrationStatus


def enqueue_integration_event(
    *,
    source: str,
    event_type: str,
    payload: dict | None,
    target: str = "",
    direction: str = str(IntegrationDirection.OUTBOUND),
    status: str = str(IntegrationStatus.PENDING),
    external_id: str = "",
) -> IntegrationEvent:
    return IntegrationEvent.objects.create(
        direction=direction,
        source=source,
        target=target,
        event_type=event_type,
        external_id=external_id,
        payload=dict(payload or {}),
        status=status,
    )
