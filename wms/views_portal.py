"""Portal views re-exported for URL routing."""

from .views_portal_account import (
    portal_account,
    portal_account_request,
    portal_recipients,
)
from .views_portal_auth import (
    portal_change_password,
    portal_login,
    portal_logout,
    portal_set_password,
)
from .views_portal_orders import (
    portal_dashboard,
    portal_order_create,
    portal_order_detail,
)

AUTH_EXPORTS = (
    "portal_login",
    "portal_logout",
    "portal_set_password",
    "portal_change_password",
)

ORDER_EXPORTS = (
    "portal_dashboard",
    "portal_order_create",
    "portal_order_detail",
)

ACCOUNT_EXPORTS = (
    "portal_recipients",
    "portal_account",
    "portal_account_request",
)

__all__ = [*AUTH_EXPORTS, *ORDER_EXPORTS, *ACCOUNT_EXPORTS]
