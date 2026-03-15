from django.utils.translation import gettext_lazy as _

SHIPMENT_STATUS_LABELS = {
    "draft": _("Brouillon"),
    "picking": _("En cours"),
    "packed": _("Disponible"),
    "planned": _("Planifié"),
    "shipped": _("Expédié"),
    "received_correspondent": _("Reçu escale"),
    "delivered": _("Livré"),
}

ORDER_STATUS_LABELS = {
    "draft": _("Brouillon"),
    "reserved": _("Réservée"),
    "preparing": _("En préparation"),
    "ready": _("Prête"),
    "cancelled": _("Annulée"),
}

ORDER_REVIEW_STATUS_LABELS = {
    "pending_validation": _("En attente de validation"),
    "approved": _("Validée"),
    "changes_requested": _("Modifications demandées"),
    "rejected": _("Refusée"),
}


def _status_value(value, attr_name):
    if hasattr(value, attr_name):
        return getattr(value, attr_name, "") or ""
    return value or ""


def _present_status(value, *, labels, domain, is_disputed=False):
    status_value = str(value or "").strip()
    label = labels.get(status_value, status_value or "-")
    if is_disputed and status_value:
        label = _("Litige - %(label)s") % {"label": label}
    return {
        "value": status_value,
        "label": str(label),
        "domain": domain,
        "is_disputed": bool(is_disputed),
    }


def present_shipment_status(shipment_or_status, *, is_disputed=None):
    status_value = _status_value(shipment_or_status, "status")
    disputed_value = (
        getattr(shipment_or_status, "is_disputed", False) if is_disputed is None else is_disputed
    )
    return _present_status(
        status_value,
        labels=SHIPMENT_STATUS_LABELS,
        domain="shipment",
        is_disputed=disputed_value,
    )


def present_order_status(order_or_status):
    return _present_status(
        _status_value(order_or_status, "status"),
        labels=ORDER_STATUS_LABELS,
        domain="order",
    )


def present_order_review_status(order_or_status):
    return _present_status(
        _status_value(order_or_status, "review_status"),
        labels=ORDER_REVIEW_STATUS_LABELS,
        domain="order_review",
    )


def present_order_shipment_status(order):
    shipment = getattr(order, "shipment", None)
    if shipment is None:
        return {
            "value": "",
            "label": "-",
            "domain": "shipment",
            "is_disputed": False,
        }
    return present_shipment_status(shipment)
