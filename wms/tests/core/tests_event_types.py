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

    def test_build_order_status_changed_event_sets_order_scope(self):
        from wms.events.publishers import build_order_status_changed_event
        from wms.events.types import EVENT_ORDER_STATUS_CHANGED

        event = build_order_status_changed_event(
            order_id=3,
            old_status="draft",
            new_status="ready",
        )

        self.assertEqual(event.event_type, EVENT_ORDER_STATUS_CHANGED)
        self.assertEqual(event.scope_type, "order")
        self.assertEqual(event.scope_id, "3")

    def test_build_pilotage_refresh_requested_event_uses_pilotage_scope(self):
        from wms.events.publishers import build_pilotage_refresh_requested_event
        from wms.events.types import EVENT_PILOTAGE_REFRESH_REQUESTED

        event = build_pilotage_refresh_requested_event(scope="global")

        self.assertEqual(event.event_type, EVENT_PILOTAGE_REFRESH_REQUESTED)
        self.assertEqual(event.scope_type, "pilotage")
        self.assertEqual(event.scope_id, "global")

    def test_build_planning_artifact_exported_event_sets_version_scope(self):
        from wms.events.publishers import build_planning_artifact_exported_event
        from wms.events.types import EVENT_PLANNING_ARTIFACT_EXPORTED

        event = build_planning_artifact_exported_event(
            version_id=9,
            artifact_type="planning_pdf",
        )

        self.assertEqual(event.event_type, EVENT_PLANNING_ARTIFACT_EXPORTED)
        self.assertEqual(event.scope_type, "planning_version")
        self.assertEqual(event.scope_id, "9")
