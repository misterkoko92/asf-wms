from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .contact_payloads import build_shipper_contact_payload
from .models import Order, PublicOrderLink
from .order_helpers import (

    build_carton_format_data,
    build_order_line_estimates,
    build_order_line_items,
)
from .portal_helpers import get_default_carton_format
from .public_order_handlers import create_public_order, send_public_order_notifications
from .scan_helpers import build_product_selection_data, parse_int as parse_int_safe
from .services import StockError


@require_http_methods(["GET"])
def scan_public_order_summary(request, token, order_id):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    order = (
        Order.objects.select_related("recipient_contact")
        .prefetch_related("lines__product")
        .filter(id=order_id, public_link=link)
        .first()
    )
    if not order:
        raise Http404

    carton_format = get_default_carton_format()
    line_rows, total_cartons = build_order_line_estimates(
        order.lines.all(),
        carton_format,
        estimate_key="cartons_estimated",
    )

    return render(
        request,
        "print/order_summary.html",
        {
            "order": order,
            "line_rows": line_rows,
            "total_cartons": total_cartons,
            "carton_format": carton_format,
        },
    )


@require_http_methods(["GET", "POST"])
def scan_public_order(request, token):
    link = (
        PublicOrderLink.objects.filter(token=token, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not link or (link.expires_at and link.expires_at < timezone.now()):
        raise Http404

    product_options, product_by_id, available_by_id = build_product_selection_data()

    contact_payload = build_shipper_contact_payload()

    form_data = {
        "association_name": "",
        "association_email": "",
        "association_phone": "",
        "association_line1": "",
        "association_line2": "",
        "association_postal_code": "",
        "association_city": "",
        "association_country": "France",
        "association_notes": "",
        "association_contact_id": "",
    }
    errors = []
    line_errors = {}
    line_quantities = {}
    summary_url = None
    summary_order_id = parse_int_safe(request.GET.get("order"))
    if summary_order_id:
        summary_url = reverse(
            "scan:scan_public_order_summary", args=[token, summary_order_id]
        )

    if request.method == "POST":
        form_data.update(
            {
                "association_name": (request.POST.get("association_name") or "").strip(),
                "association_email": (request.POST.get("association_email") or "").strip(),
                "association_phone": (request.POST.get("association_phone") or "").strip(),
                "association_line1": (request.POST.get("association_line1") or "").strip(),
                "association_line2": (request.POST.get("association_line2") or "").strip(),
                "association_postal_code": (
                    request.POST.get("association_postal_code") or ""
                ).strip(),
                "association_city": (request.POST.get("association_city") or "").strip(),
                "association_country": (
                    request.POST.get("association_country") or "France"
                ).strip(),
                "association_notes": (request.POST.get("association_notes") or "").strip(),
                "association_contact_id": (
                    request.POST.get("association_contact_id") or ""
                ).strip(),
            }
        )
        if not form_data["association_name"]:
            errors.append("Nom de l'association requis.")
        if not form_data["association_line1"]:
            errors.append("Adresse requise.")

        line_items, line_quantities, line_errors = build_order_line_items(
            request.POST,
            product_options=product_options,
            product_by_id=product_by_id,
            available_by_id=available_by_id,
        )

        if not line_items:
            errors.append("Ajoutez au moins un produit.")

        if not errors and not line_errors:
            try:
                order, contact = create_public_order(
                    request=request,
                    link=link,
                    form_data=form_data,
                    line_items=line_items,
                )
            except StockError as exc:
                errors.append(str(exc))
            else:
                send_public_order_notifications(
                    request,
                    token=token,
                    order=order,
                    form_data=form_data,
                    contact=contact,
                )
                messages.success(
                    request,
                    "Commande envoyee. L'equipe ASF va la traiter rapidement.",
                )
                return redirect(
                    f"{reverse('scan:scan_public_order', args=[token])}?order={order.id}"
                )

    carton_format = get_default_carton_format()
    carton_data = build_carton_format_data(carton_format)

    return render(
        request,
        "scan/public_order.html",
        {
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
        },
    )
