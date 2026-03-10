class PlanningFlightProviderError(RuntimeError):
    """Raised when a planning flight provider fails to fetch or normalize data."""


class PlanningFlightProviderConfigurationError(PlanningFlightProviderError):
    """Raised when a planning flight provider is misconfigured."""


class UnknownPlanningFlightProviderError(PlanningFlightProviderConfigurationError):
    """Raised when the configured planning flight provider is unsupported."""


class PlanningFlightProvider:
    def fetch_flights(self, *, start_date, end_date):
        raise NotImplementedError("Configure a concrete planning flight provider.")
