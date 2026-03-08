from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from wms.billing_exchange_rates import resolve_exchange_rate


class BillingExchangeRateTests(SimpleTestCase):
    @patch("wms.billing_exchange_rates._fetch_ecb_reference_rates")
    def test_ecb_backed_currency_prefills_rate(self, mock_fetch_rates):
        mock_fetch_rates.return_value = (
            date(2026, 3, 6),
            {
                "USD": Decimal("1.083500"),
                "CHF": Decimal("0.954300"),
            },
        )

        resolution = resolve_exchange_rate(document_currency="USD", base_currency="EUR")

        self.assertEqual(resolution.rate, Decimal("1.083500"))
        self.assertEqual(resolution.provider_name, "ECB")
        self.assertEqual(resolution.as_of_date, date(2026, 3, 6))
        self.assertFalse(resolution.requires_manual_entry)

    def test_manual_only_currency_returns_no_remote_rate(self):
        resolution = resolve_exchange_rate(document_currency="XOF", base_currency="EUR")

        self.assertIsNone(resolution.rate)
        self.assertIsNone(resolution.provider_name)
        self.assertIsNone(resolution.as_of_date)
        self.assertTrue(resolution.requires_manual_entry)

    @patch("wms.billing_exchange_rates._fetch_ecb_reference_rates")
    def test_auto_currency_falls_back_to_manual_when_fetch_fails(self, mock_fetch_rates):
        mock_fetch_rates.side_effect = RuntimeError("ECB unavailable")

        resolution = resolve_exchange_rate(document_currency="CHF", base_currency="EUR")

        self.assertIsNone(resolution.rate)
        self.assertIsNone(resolution.provider_name)
        self.assertTrue(resolution.requires_manual_entry)
        self.assertEqual(resolution.error_message, "Unable to fetch ECB exchange rate.")
