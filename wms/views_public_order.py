from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .contact_payloads import build_shipper_contact_payload
from .models import Order
from .order_helpers import (
    build_carton_format_data,
    build_order_line_estimates,
    build_order_line_items,
)
from .portal_helpers import get_default_carton_format
from .public_link_helpers import get_active_public_order_link_or_404
from .public_order_handlers import create_public_order, send_public_order_notifications
from .scan_helpers import build_product_selection_data, parse_int as parse_int_safe
from .services import StockError

TEMPLATE_PUBLIC_ORDER = "scan/public_order.html"
TEMPLATE_PUBLIC_ORDER_SUMMARY = "print/order_summary.html"

DEFAULT_COUNTRY = "France"
MESSAGE_PUBLIC_ORDER_SENT = "Commande envoyée. L'équipe ASF va la traiter rapidement."

ERROR_ASSOCIATION_NAME_REQUIRED = "Nom de l'association requis."
ERROR_ASSOCIATION_ADDRESS_REQUIRED = "Adresse requise."
ERROR_PRODUCTS_REQUIRED = "Ajoutez au moins un produit."
ERROR_THROTTLE_LIMIT = (
    "Une commande récente a déjà été envoyée. Merci de patienter quelques minutes."
)

PUBLIC_ORDER_THROTTLE_SECONDS_DEFAULT = 300


def _get_public_order_or_404(link, order_id):
    order = (
        Order.objects.select_related("recipient_contact")
        .prefetch_related("lines__product")
        .filter(id=order_id, public_link=link)
        .first()
    )
    if not order:
        raise Http404
    return order


def _build_public_order_form_defaults():
    return {
        "association_name": "",
        "association_email": "",
        "association_phone": "",
        "association_line1": "",
        "association_line2": "",
        "association_postal_code": "",
        "association_city": "",
        "association_country": DEFAULT_COUNTRY,
        "association_notes": "",
        "association_contact_id": "",
    }


def _extract_public_order_form_data(post_data):
    return {
        "association_name": (post_data.get("association_name") or "").strip(),
        "association_email": (post_data.get("association_email") or "").strip(),
        "association_phone": (post_data.get("association_phone") or "").strip(),
        "association_line1": (post_data.get("association_line1") or "").strip(),
        "association_line2": (post_data.get("association_line2") or "").strip(),
        "association_postal_code": (post_data.get("association_postal_code") or "").strip(),
        "association_city": (post_data.get("association_city") or "").strip(),
        "association_country": (post_data.get("association_country") or DEFAULT_COUNTRY).strip(),
        "association_notes": (post_data.get("association_notes") or "").strip(),
        "association_contact_id": (post_data.get("association_contact_id") or "").strip(),
    }


def _build_summary_url(token, order_query):
    summary_order_id = parse_int_safe(order_query)
    if not summary_order_id:
        return None
    return reverse("scan:scan_public_order_summary", args=[token, summary_order_id])


def _get_client_ip(request):
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def _get_public_order_throttle_seconds():
    raw_value = getattr(
        settings,
        "PUBLIC_ORDER_THROTTLE_SECONDS",
        PUBLIC_ORDER_THROTTLE_SECONDS_DEFAULT,
    )
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return PUBLIC_ORDER_THROTTLE_SECONDS_DEFAULT
    return max(0, value)


def _get_throttle_keys(*, token, email, client_ip):
    token_key = str(token)
    normalized_email = (email or "").strip().lower() or "unknown"
    normalized_ip = (client_ip or "").strip() or "unknown"
    return (
        f"public-order:{token_key}:email:{normalized_email}",
        f"public-order:{token_key}:ip:{normalized_ip}",
    )


def _reserve_throttle_slot(*, token, email, client_ip):
    timeout = _get_public_order_throttle_seconds()
    if timeout <= 0:
        return True

    email_key, ip_key = _get_throttle_keys(
        token=token,
        email=email,
        client_ip=client_ip,
    )
    email_reserved = cache.add(email_key, "1", timeout=timeout)
    ip_reserved = cache.add(ip_key, "1", timeout=timeout)
    if email_reserved and ip_reserved:
        return True
    if email_reserved and not ip_reserved:
        cache.delete(email_key)
    if ip_reserved and not email_reserved:
        cache.delete(ip_key)
    return False


def _release_throttle_slot(*, token, email, client_ip):
    timeout = _get_public_order_throttle_seconds()
    if timeout <= 0:
        return
    email_key, ip_key = _get_throttle_keys(
        token=token,
        email=email,
        client_ip=client_ip,
    )
    cache.delete(email_key)
    cache.delete(ip_key)


def _build_public_order_context(
    *,
    link,
    product_options,
    contact_payload,
    form_data,
    errors,
    line_errors,
    line_quantities,
    summary_url,
):
    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)
    return {
        "link": link,
        "products": product_options,
        "product_data": product_options,
        "contacts": contact_payload,
        "form_data": form_data,
        "errors": errors,
        "line_errors": line_errors,
        "line_quantities": line_quantities,
        "carton_format": carton_data,
        "summary_url": summary_url,
    }


@require_http_methods(["GET"])
def scan_public_order_summary(request, token, order_id):
    link = get_active_public_order_link_or_404(token)
    order = _get_public_order_or_404(link, order_id)

    carton_format = get_default_carton_format()
    line_rows, total_cartons = build_order_line_estimates(
        order.lines.all(),
        carton_format,
        estimate_key="cartons_estimated",
    )

    return render(
        request,
        TEMPLATE_PUBLIC_ORDER_SUMMARY,
        {
            "order": order,
            "line_rows": line_rows,
            "total_cartons": total_cartons,
            "carton_format": carton_format,
        },
    )


@require_http_methods(["GET", "POST"])
def scan_public_order(request, token):
    link = get_active_public_order_link_or_404(token)

    product_options, product_by_id, available_by_id = build_product_selection_data()

    contact_payload = build_shipper_contact_payload()

    form_data = _build_public_order_form_defaults()
    errors = []
    line_errors = {}
    line_quantities = {}
    summary_url = _build_summary_url(token, request.GET.get("order"))

    if request.method == "POST":
        form_data = _extract_public_order_form_data(request.POST)
        if not form_data["association_name"]:
            errors.append(ERROR_ASSOCIATION_NAME_REQUIRED)
        if not form_data["association_line1"]:
            errors.append(ERROR_ASSOCIATION_ADDRESS_REQUIRED)

        line_items, line_quantities, line_errors = build_order_line_items(
            request.POST,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )

        if not line_items:
            errors.append(ERROR_PRODUCTS_REQUIRED)

        client_ip = ""
        if not errors and not line_errors:
            client_ip = _get_client_ip(request)
            if not _reserve_throttle_slot(
                token=token,
                email=form_data["association_email"],
                client_ip=client_ip,
            ):
                errors.append(ERROR_THROTTLE_LIMIT)

        if not errors and not line_errors:
            try:
                order, contact = create_public_order(
                    link=link,
                    form_data=form_data,
                    line_items=line_items,
                )
            except StockError as exc:
                _release_throttle_slot(
                    token=token,
                    email=form_data["association_email"],
                    client_ip=client_ip,
                )
                errors.append(str(exc))
            except Exception:
                _release_throttle_slot(
                    token=token,
                    email=form_data["association_email"],
                    client_ip=client_ip,
                )
                raise
            else:
                send_public_order_notifications(
                    request,
                    token=token,
                    order=order,
                    form_data=form_data,
                    contact=contact,
                )
                messages.success(request, MESSAGE_PUBLIC_ORDER_SENT)
                return redirect(
                    f"{reverse('scan:scan_public_order', args=[token])}?order={order.id}"
                )

    return render(
        request,
        TEMPLATE_PUBLIC_ORDER,
        _build_public_order_context(
            link=link,
            product_options=product_options,
            contact_payload=contact_payload,
            form_data=form_data,
            errors=errors,
            line_errors=line_errors,
            line_quantities=line_quantities,
            summary_url=summary_url,
        ),
    )
