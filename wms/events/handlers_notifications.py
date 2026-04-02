from wms.events.types import RuntimeEvent


def _shipment_status_label(signal_helpers, raw_status):
    try:
        return signal_helpers.ShipmentStatus(raw_status).label
    except ValueError:
        return raw_status


def _tracking_status_label(signal_helpers, raw_status):
    return dict(signal_helpers.ShipmentTrackingStatus.choices).get(raw_status, raw_status)


def handle_shipment_status_changed_event(*, event: RuntimeEvent, shipment) -> None:
    from wms import signals as signal_helpers

    previous_status = event.payload["old_status"]
    new_status = event.payload["new_status"]
    signal_helpers.log_shipment_status_transition(
        shipment=shipment,
        previous_status=previous_status,
        new_status=new_status,
        source="shipment_post_save_signal",
    )
    old_label = _shipment_status_label(signal_helpers, previous_status)
    new_label = _shipment_status_label(signal_helpers, new_status)
    admin_recipients = signal_helpers._shipment_status_admin_recipients()
    if admin_recipients:
        admin_url = signal_helpers._build_site_url(
            signal_helpers.reverse("admin:wms_shipment_change", args=[shipment.id])
        )
        message = signal_helpers.render_to_string(
            "emails/shipment_status_admin_notification.txt",
            {
                "shipment_reference": shipment.reference,
                "old_status": old_label,
                "new_status": new_label,
                "destination_label": str(shipment.destination)
                if shipment.destination
                else shipment.destination_address,
                "changed_at": signal_helpers.timezone.localtime(signal_helpers.timezone.now()),
                "tracking_url": shipment.get_tracking_url(),
                "admin_url": admin_url,
            },
        )
        signal_helpers.transaction.on_commit(
            lambda: signal_helpers.send_or_enqueue_email_safe(
                subject=signal_helpers._("ASF WMS - Expédition %(reference)s : statut mis à jour")
                % {"reference": shipment.reference},
                message=message,
                recipient=admin_recipients,
            )
        )
    if shipment.status in signal_helpers.SHIPMENT_CONTACT_NOTIFICATION_STATUSES:
        signal_helpers._queue_shipment_party_notification(
            shipment=shipment,
            old_label=old_label,
            new_label=new_label,
        )
    if shipment.status == signal_helpers.ShipmentStatus.PLANNED:
        signal_helpers._queue_shipment_correspondant_notification(
            shipment=shipment,
            old_label=old_label,
            new_label=new_label,
            tracking_status_label=_tracking_status_label(
                signal_helpers,
                signal_helpers.ShipmentTrackingStatus.PLANNED,
            ),
        )
    if shipment.status == signal_helpers.ShipmentStatus.DELIVERED:
        signal_helpers._notify_shipment_delivery(shipment)


def handle_tracking_event_created_event(*, event: RuntimeEvent, tracking_event) -> None:
    from wms import signals as signal_helpers

    signal_helpers.log_shipment_tracking_event(
        tracking_event=tracking_event,
        user=getattr(tracking_event, "created_by", None),
    )
    shipment = tracking_event.shipment
    recipients = signal_helpers.get_admin_emails()
    if recipients:
        admin_url = signal_helpers._build_site_url(
            signal_helpers.reverse("admin:wms_shipment_change", args=[shipment.id])
        )
        message = signal_helpers.render_to_string(
            "emails/shipment_tracking_admin_notification.txt",
            {
                "shipment_reference": shipment.reference,
                "status": tracking_event.get_status_display(),
                "actor_name": tracking_event.actor_name,
                "actor_structure": tracking_event.actor_structure,
                "comments": tracking_event.comments or "-",
                "event_time": signal_helpers.timezone.localtime(tracking_event.created_at),
                "tracking_url": shipment.get_tracking_url(),
                "admin_url": admin_url,
            },
        )
        signal_helpers.transaction.on_commit(
            lambda: signal_helpers.send_or_enqueue_email_safe(
                subject=signal_helpers._("ASF WMS - Suivi expédition %(reference)s")
                % {"reference": shipment.reference},
                message=message,
                recipient=recipients,
            )
        )
    tracking_status = getattr(tracking_event, "status", "")
    if tracking_status in signal_helpers.SHIPMENT_CORRESPONDANT_TRACKING_STATUSES:
        tracking_status_label = tracking_status
        if hasattr(tracking_event, "get_status_display"):
            tracking_status_label = tracking_event.get_status_display()
        signal_helpers._queue_shipment_correspondant_notification(
            shipment=shipment,
            old_label="-",
            new_label=tracking_status_label,
            tracking_status_label=tracking_status_label,
        )
