from django.test import SimpleTestCase

from wms.policies.pilotage import normalize_planning_thresholds
from wms.policies.planning import classify_planning_load_state
from wms.policies.shipment_parties import default_recipient_shipper_name
from wms.policies.sla import classify_sla_delay
from wms.shipment_party_setup import PRIORITY_SHIPPER_NAME


class PoliciesTests(SimpleTestCase):
    def test_classify_planning_load_state_marks_overload(self):
        self.assertEqual(
            classify_planning_load_state(
                101,
                tension_pct=80,
                critical_pct=95,
            ),
            "overload",
        )

    def test_classify_sla_delay_marks_persistent_after_double_threshold(self):
        self.assertEqual(
            classify_sla_delay(
                delay_hours=145,
                threshold_hours=72,
            ),
            "persistent",
        )

    def test_normalize_planning_thresholds_keeps_critical_above_tension(self):
        self.assertEqual(
            normalize_planning_thresholds(
                tension_pct=90,
                critical_pct=75,
            ),
            (90, 90),
        )

    def test_default_recipient_shipper_name_uses_uppercase_priority_shipper(self):
        self.assertEqual(default_recipient_shipper_name(), PRIORITY_SHIPPER_NAME.upper())
