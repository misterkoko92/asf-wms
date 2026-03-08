from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from urllib import request

from defusedxml import ElementTree

ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_AUTO_CURRENCIES = {"USD", "CHF", "CNY"}
MANUAL_ONLY_CURRENCIES = {"VND", "XOF", "XAF"}
SUPPORTED_BILLING_CURRENCIES = ("EUR", "USD", "CHF", "CNY", "VND", "XOF", "XAF")
SIX_DECIMAL_PLACES = Decimal("0.000001")


@dataclass(frozen=True)
class ExchangeRateResolution:
    document_currency: str
    base_currency: str
    rate: Decimal | None
    provider_name: str | None
    as_of_date: date | None
    requires_manual_entry: bool
    error_message: str = ""


def _fetch_ecb_reference_rates():
    http_request = request.Request(
        ECB_DAILY_RATES_URL,
        headers={"User-Agent": "ASF-WMS Billing/1.0"},
    )
    with request.urlopen(http_request, timeout=10) as response:  # nosec B310
        payload = response.read()

    root = ElementTree.fromstring(payload)
    as_of_date = None
    rates = {}
    for node in root.iter():
        if as_of_date is None and node.attrib.get("time"):
            as_of_date = date.fromisoformat(node.attrib["time"])
        currency = node.attrib.get("currency")
        rate = node.attrib.get("rate")
        if currency and rate:
            rates[currency.upper()] = Decimal(rate).quantize(SIX_DECIMAL_PLACES)
    return as_of_date, rates


def resolve_exchange_rate(*, document_currency, base_currency="EUR"):
    normalized_document_currency = (document_currency or "EUR").upper()
    normalized_base_currency = (base_currency or "EUR").upper()

    if normalized_document_currency == normalized_base_currency:
        return ExchangeRateResolution(
            document_currency=normalized_document_currency,
            base_currency=normalized_base_currency,
            rate=Decimal("1.000000"),
            provider_name=None,
            as_of_date=None,
            requires_manual_entry=False,
        )

    if normalized_document_currency in MANUAL_ONLY_CURRENCIES:
        return ExchangeRateResolution(
            document_currency=normalized_document_currency,
            base_currency=normalized_base_currency,
            rate=None,
            provider_name=None,
            as_of_date=None,
            requires_manual_entry=True,
        )

    if normalized_base_currency != "EUR" or normalized_document_currency not in ECB_AUTO_CURRENCIES:
        return ExchangeRateResolution(
            document_currency=normalized_document_currency,
            base_currency=normalized_base_currency,
            rate=None,
            provider_name=None,
            as_of_date=None,
            requires_manual_entry=True,
        )

    try:
        as_of_date, rates = _fetch_ecb_reference_rates()
    except Exception:
        return ExchangeRateResolution(
            document_currency=normalized_document_currency,
            base_currency=normalized_base_currency,
            rate=None,
            provider_name=None,
            as_of_date=None,
            requires_manual_entry=True,
            error_message="Unable to fetch ECB exchange rate.",
        )

    rate = rates.get(normalized_document_currency)
    if rate is None:
        return ExchangeRateResolution(
            document_currency=normalized_document_currency,
            base_currency=normalized_base_currency,
            rate=None,
            provider_name=None,
            as_of_date=as_of_date,
            requires_manual_entry=True,
            error_message="Unable to fetch ECB exchange rate.",
        )

    return ExchangeRateResolution(
        document_currency=normalized_document_currency,
        base_currency=normalized_base_currency,
        rate=rate,
        provider_name="ECB",
        as_of_date=as_of_date,
        requires_manual_entry=False,
    )
