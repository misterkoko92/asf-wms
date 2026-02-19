from unittest import mock

from django.test import TestCase

from wms.carton_status_events import set_carton_status
from wms.models import Carton, CartonStatus


class CartonStatusEventsLoggingTests(TestCase):
    def test_set_carton_status_logs_structured_transition(self):
        carton = Carton.objects.create(code="CT-OBS-1", status=CartonStatus.DRAFT)

        with mock.patch("wms.carton_status_events.log_carton_status_transition") as log_mock:
            changed = set_carton_status(
                carton=carton,
                new_status=CartonStatus.PICKING,
                reason="unit_test",
            )

        self.assertTrue(changed)
        log_mock.assert_called_once_with(
            carton=carton,
            previous_status=CartonStatus.DRAFT,
            new_status=CartonStatus.PICKING,
            reason="unit_test",
            user=None,
            source="set_carton_status",
        )
