from django.test import SimpleTestCase


class EventTypesTests(SimpleTestCase):
    def test_build_shipment_status_changed_event_sets_type(self):
        from wms.events.publishers import build_shipment_status_changed_event
        from wms.events.types import EVENT_SHIPMENT_STATUS_CHANGED

        event = build_shipment_status_changed_event(
            shipment_id=1,
            old_status="planned",
            new_status="shipped",
        )

        self.assertEqual(event.event_type, EVENT_SHIPMENT_STATUS_CHANGED)
        self.assertEqual(event.scope_type, "shipment")
        self.assertEqual(event.scope_id, "1")
