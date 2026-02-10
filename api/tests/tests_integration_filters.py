from datetime import datetime

from django.db.models import Q
from django.test import SimpleTestCase

from api.v1.integration_filters import (
    _normalize_param,
    apply_integration_destination_filters,
    apply_integration_event_filters,
    apply_integration_shipment_filters,
)


class _FakeQuerySet:
    def __init__(self):
        self.calls = []

    def filter(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self


class IntegrationFiltersTests(SimpleTestCase):
    def test_normalize_param(self):
        params = {"status": " packed ", "empty": None}
        self.assertEqual(_normalize_param(params, "status"), "packed")
        self.assertEqual(_normalize_param(params, "empty"), "")
        self.assertEqual(_normalize_param(params, "missing"), "")

    def test_apply_integration_shipment_filters_full_flow(self):
        queryset = _FakeQuerySet()
        params = {"status": " packed ", "destination": " PAR ", "since": "2026-01-10T12:00:00"}
        aware_dt = object()

        from unittest import mock

        with mock.patch("api.v1.integration_filters.timezone.is_naive", return_value=True):
            with mock.patch(
                "api.v1.integration_filters.timezone.make_aware",
                return_value=aware_dt,
            ):
                out = apply_integration_shipment_filters(queryset, params)

        self.assertIs(out, queryset)
        self.assertEqual(len(queryset.calls), 3)
        self.assertEqual(queryset.calls[0][1], {"status": "packed"})
        self.assertTrue(isinstance(queryset.calls[1][0][0], Q))
        self.assertEqual(queryset.calls[2][1], {"created_at__gte": aware_dt})

    def test_apply_integration_shipment_filters_invalid_since_is_ignored(self):
        queryset = _FakeQuerySet()
        params = {"status": "shipped", "since": "invalid-date"}
        out = apply_integration_shipment_filters(queryset, params)

        self.assertIs(out, queryset)
        self.assertEqual(len(queryset.calls), 1)
        self.assertEqual(queryset.calls[0][1], {"status": "shipped"})

    def test_apply_integration_destination_filters(self):
        queryset = _FakeQuerySet()
        out = apply_integration_destination_filters(queryset, {"active": "1"})
        self.assertIs(out, queryset)
        self.assertEqual(queryset.calls, [((), {"is_active": True})])

        queryset = _FakeQuerySet()
        out = apply_integration_destination_filters(queryset, {"active": ""})
        self.assertIs(out, queryset)
        self.assertEqual(queryset.calls, [])

    def test_apply_integration_event_filters(self):
        queryset = _FakeQuerySet()
        params = {
            "direction": "out",
            "status": "success",
            "source": "wms",
            "event_type": "shipment_created",
        }
        out = apply_integration_event_filters(queryset, params)

        self.assertIs(out, queryset)
        self.assertEqual(
            queryset.calls,
            [
                ((), {"direction": "out"}),
                ((), {"status": "success"}),
                ((), {"source": "wms"}),
                ((), {"event_type": "shipment_created"}),
            ],
        )

        queryset = _FakeQuerySet()
        out = apply_integration_event_filters(queryset, {"direction": "  "})
        self.assertIs(out, queryset)
        self.assertEqual(queryset.calls, [])
