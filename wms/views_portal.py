"""Portal views re-exported for URL routing."""

from .views_portal_account import (
    portal_account,
    portal_account_request,
    portal_recipient_detail,
    portal_recipient_preferences,
    portal_recipient_profile,
    portal_recipients,
)
from .views_portal_auth import (
    portal_change_password,
    portal_forgot_password,
    portal_login,
    portal_logout,
    portal_scope_select,
    portal_set_password,
)
from .views_portal_billing import (
    portal_billing,
    portal_billing_detail,
)
from .views_portal_misc import portal_faq
from .views_portal_orders import (
    portal_dashboard,
    portal_order_create,
    portal_order_detail,
)

AUTH_EXPORTS = (
    "portal_login",
    "portal_scope_select",
    "portal_forgot_password",
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
    "portal_recipient_detail",
    "portal_recipient_profile",
    "portal_recipient_preferences",
    "portal_account",
    "portal_account_request",
)

BILLING_EXPORTS = (
    "portal_billing",
    "portal_billing_detail",
)

MISC_EXPORTS = ("portal_faq",)

__all__ = [*AUTH_EXPORTS, *ORDER_EXPORTS, *ACCOUNT_EXPORTS, *BILLING_EXPORTS, *MISC_EXPORTS]
