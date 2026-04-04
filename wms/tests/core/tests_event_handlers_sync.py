from unittest import mock

from django.test import SimpleTestCase

from wms.events.handlers_sync import (
    handle_default_shipper_links_for_destination_event,
    handle_default_shipper_links_for_recipient_organization_event,
    handle_destination_correspondent_recipient_support_event,
)
from wms.events.types import RuntimeEvent


class EventHandlersSyncTests(SimpleTestCase):
    def test_default_shipper_links_for_recipient_organization_event_runs_on_commit(self):
        event = RuntimeEvent(
            event_type="shipment_parties.default_shipper_links_for_recipient_organization",
            scope_type="recipient_organization",
            scope_id="17",
        )
        with (
            mock.patch(
                "wms.events.handlers_sync.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ),
            mock.patch(
                "wms.events.handlers_sync.ensure_default_shipper_links_for_recipient_organization_id"
            ) as ensure_mock,
        ):
            handle_default_shipper_links_for_recipient_organization_event(event=event)

        ensure_mock.assert_called_once_with(17)

    def test_default_shipper_links_for_destination_event_runs_on_commit(self):
        event = RuntimeEvent(
            event_type="shipment_parties.default_shipper_links_for_destination",
            scope_type="destination",
            scope_id="21",
        )
        with (
            mock.patch(
                "wms.events.handlers_sync.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ),
            mock.patch(
                "wms.events.handlers_sync.ensure_default_shipper_links_for_destination_id"
            ) as ensure_mock,
        ):
            handle_default_shipper_links_for_destination_event(event=event)

        ensure_mock.assert_called_once_with(21)

    def test_destination_correspondent_support_handler_ignores_missing_destination(self):
        event = RuntimeEvent(
            event_type="destination.correspondent_recipient_support_requested",
            scope_type="destination",
            scope_id="29",
        )
        filter_mock = mock.Mock()
        filter_mock.select_related.return_value.first.return_value = None
        with (
            mock.patch(
                "wms.events.handlers_sync.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ),
            mock.patch(
                "wms.events.handlers_sync.Destination.objects.filter", return_value=filter_mock
            ),
            mock.patch(
                "wms.events.handlers_sync.ensure_destination_correspondent_recipient_ready"
            ) as ensure_mock,
        ):
            handle_destination_correspondent_recipient_support_event(event=event)

        ensure_mock.assert_not_called()

    def test_destination_correspondent_support_handler_syncs_existing_destination(self):
        event = RuntimeEvent(
            event_type="destination.correspondent_recipient_support_requested",
            scope_type="destination",
            scope_id="33",
        )
        destination = object()
        filter_mock = mock.Mock()
        filter_mock.select_related.return_value.first.return_value = destination
        with (
            mock.patch(
                "wms.events.handlers_sync.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ),
            mock.patch(
                "wms.events.handlers_sync.Destination.objects.filter", return_value=filter_mock
            ),
            mock.patch(
                "wms.events.handlers_sync.ensure_destination_correspondent_recipient_ready"
            ) as ensure_mock,
        ):
            handle_destination_correspondent_recipient_support_event(event=event)

        ensure_mock.assert_called_once_with(destination)
