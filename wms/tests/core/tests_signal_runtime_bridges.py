from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from wms.signals import (
    _sync_default_shipper_links_for_destination,
    _sync_default_shipper_links_for_recipient_organization,
    _sync_destination_correspondent_recipient_support,
)


class SignalRuntimeBridgeTests(SimpleTestCase):
    def test_sync_default_shipper_links_for_recipient_organization_delegates_to_handler(self):
        instance = SimpleNamespace(id=12, is_active=True)
        with mock.patch(
            "wms.events.handlers_sync.handle_default_shipper_links_for_recipient_organization_event"
        ) as handler_mock:
            _sync_default_shipper_links_for_recipient_organization(
                None,
                instance,
                created=False,
            )
        handler_mock.assert_called_once()

    def test_sync_default_shipper_links_for_destination_delegates_to_handler(self):
        instance = SimpleNamespace(id=24, is_active=True)
        with mock.patch(
            "wms.events.handlers_sync.handle_default_shipper_links_for_destination_event"
        ) as handler_mock:
            _sync_default_shipper_links_for_destination(None, instance, created=False)
        handler_mock.assert_called_once()

    def test_sync_destination_correspondent_recipient_support_delegates_to_handler(self):
        instance = SimpleNamespace(id=36, is_active=True, correspondent_contact_id=9)
        with mock.patch(
            "wms.events.handlers_sync.handle_destination_correspondent_recipient_support_event"
        ) as handler_mock:
            _sync_destination_correspondent_recipient_support(None, instance, created=False)
        handler_mock.assert_called_once()
