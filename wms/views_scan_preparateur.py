from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ScanPackUnknownProductForm
from .pack_handlers import create_preparateur_unknown_product_from_pack
from .preparateur_orders import clear_preparateur_selected_order
from .preparateur_rangement import (
    PREPARATEUR_RANGEMENT_BATCH_LIMIT,
    PREPARATEUR_RANGEMENT_MODE_RECEIPT,
    PREPARATEUR_RANGEMENT_MODE_TRANSFER,
    PREPARATEUR_RANGEMENT_MODES,
    PreparateurRangementError,
    add_created_product_to_preparateur_rangement_batch,
    add_product_to_preparateur_rangement_batch,
    clear_preparateur_rangement_batch,
    get_preparateur_rangement_batch,
    get_preparateur_rangement_mode,
    resolve_preparateur_rangement_product,
    set_default_location_for_rangement_product,
    set_preparateur_rangement_mode,
    validate_preparateur_rangement_batch,
)
from .preparateur_session import (
    build_preparateur_volunteer_label,
    build_preparateur_volunteer_queryset,
    clear_active_preparateur_volunteer,
    get_active_preparateur_volunteer,
    set_active_preparateur_volunteer,
)
from .scan_helpers import build_location_data, build_product_options
from .scan_permissions import user_is_preparateur
from .services import StockError
from .view_permissions import scan_staff_required

TEMPLATE_PREPARATEUR_HOME = "scan/preparateur_home.html"
TEMPLATE_PREPARATEUR_RANGEMENT = "scan/preparateur_rangement.html"
ACTIVE_PREPARATEUR_HOME = "preparateur_home"
ACTIVE_PREPARATEUR_RANGEMENT = "preparateur_rangement"


def _build_preparateur_home_context(*, active_volunteer):
    volunteer_options = [
        {
            "id": volunteer.id,
            "label": build_preparateur_volunteer_label(volunteer),
        }
        for volunteer in build_preparateur_volunteer_queryset()
    ]
    return {
        "active": ACTIVE_PREPARATEUR_HOME,
        "active_volunteer": active_volunteer,
        "active_volunteer_id": active_volunteer.id if active_volunteer is not None else "",
        "has_active_volunteer": active_volunteer is not None,
        "volunteer_options": volunteer_options,
    }


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_home(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_dashboard")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        volunteer_id = (request.POST.get("volunteer_id") or "").strip()
        volunteer = (
            build_preparateur_volunteer_queryset().filter(pk=volunteer_id).first()
            if volunteer_id
            else None
        )
        if volunteer is not None:
            set_active_preparateur_volunteer(request, volunteer)
        elif not action:
            clear_active_preparateur_volunteer(request)

        active_volunteer = volunteer or get_active_preparateur_volunteer(request)
        if action == "prepare_order":
            if active_volunteer is None:
                return redirect("scan:scan_preparateur_home")
            return redirect("scan:scan_preparateur_order_select")
        if action == "prepare_cartons":
            if active_volunteer is None:
                return redirect("scan:scan_preparateur_home")
            clear_preparateur_selected_order(request)
            return redirect("scan:scan_pack")
        if action == "rangement":
            if active_volunteer is None:
                return redirect("scan:scan_preparateur_home")
            return redirect("scan:scan_preparateur_rangement")
        return redirect("scan:scan_preparateur_home")

    active_volunteer = get_active_preparateur_volunteer(request)
    return render(
        request,
        TEMPLATE_PREPARATEUR_HOME,
        _build_preparateur_home_context(active_volunteer=active_volunteer),
    )


@scan_staff_required
@require_http_methods(["GET"])
def scan_preparateur_pack_start(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_pack")
    clear_preparateur_selected_order(request)
    return redirect("scan:scan_pack")


def _parse_rangement_quantity(value):
    value = (value or "").strip()
    if not value:
        raise PreparateurRangementError("Quantité obligatoire.")
    try:
        quantity = int(value)
    except ValueError as exc:
        raise PreparateurRangementError("Quantité invalide.") from exc
    if quantity <= 0:
        raise PreparateurRangementError("Quantité invalide.")
    return quantity


def _build_unknown_product_form(*, source_code="", quantity=1, form=None):
    if form is not None:
        return form
    return ScanPackUnknownProductForm(
        initial={
            "unknown_product_line_index": 0,
            "unknown_product_source_code": source_code,
            "unknown_product_barcode": source_code,
            "unknown_product_initial_quantity": quantity,
        }
    )


def _build_preparateur_rangement_context(
    *,
    request,
    unknown_product_modal_open=False,
    unknown_product_form=None,
    unknown_product_source_code="",
):
    location_data = build_location_data()
    rangement_mode = get_preparateur_rangement_mode(request)
    return {
        "active": ACTIVE_PREPARATEUR_RANGEMENT,
        "rangement_batch": get_preparateur_rangement_batch(request),
        "rangement_mode": rangement_mode,
        "rangement_mode_label": PREPARATEUR_RANGEMENT_MODES.get(rangement_mode, ""),
        "rangement_modes": [
            {"value": value, "label": label} for value, label in PREPARATEUR_RANGEMENT_MODES.items()
        ],
        "unknown_product_modal_open": unknown_product_modal_open,
        "unknown_product_source_code": unknown_product_source_code,
        "unknown_product_form": unknown_product_form or ScanPackUnknownProductForm(),
        "products_json": build_product_options(compact=True),
        "location_data": location_data,
        "location_options": location_data,
    }


def _render_preparateur_rangement(request, **context_kwargs):
    return render(
        request,
        TEMPLATE_PREPARATEUR_RANGEMENT,
        _build_preparateur_rangement_context(request=request, **context_kwargs),
    )


@scan_staff_required
@require_http_methods(["GET", "POST"])
def scan_preparateur_rangement(request):
    if not user_is_preparateur(request.user):
        return redirect("scan:scan_dashboard")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "finish_batch":
            clear_preparateur_rangement_batch(request)
            messages.success(request, "Rangement terminé.")
            return redirect("scan:scan_preparateur_rangement")

        if action == "validate_batch":
            try:
                validate_preparateur_rangement_batch(request)
                messages.success(request, "Batch rangement validé.")
                return redirect("scan:scan_preparateur_rangement")
            except (PreparateurRangementError, StockError) as exc:
                messages.error(request, str(exc))
                return _render_preparateur_rangement(request)

        if action == "set_default_location":
            try:
                set_default_location_for_rangement_product(
                    request,
                    product_id=request.POST.get("product_id"),
                    location_id=request.POST.get("location_id"),
                )
                messages.success(request, "Emplacement par défaut défini.")
            except PreparateurRangementError as exc:
                messages.error(request, str(exc))
            return _render_preparateur_rangement(request)

        if action == "create_unknown_product":
            unknown_product_form = ScanPackUnknownProductForm(request.POST)
            mode = get_preparateur_rangement_mode(request) or request.POST.get("movement_mode", "")
            if mode != PREPARATEUR_RANGEMENT_MODE_RECEIPT:
                unknown_product_form.add_error(
                    None,
                    "Créer un produit inconnu est réservé au mode Entrée en stock.",
                )
                return _render_preparateur_rangement(
                    request,
                    unknown_product_modal_open=True,
                    unknown_product_form=unknown_product_form,
                    unknown_product_source_code=request.POST.get("unknown_product_source_code", ""),
                )
            if unknown_product_form.is_valid():
                try:
                    if (
                        len(get_preparateur_rangement_batch(request))
                        >= PREPARATEUR_RANGEMENT_BATCH_LIMIT
                    ):
                        raise PreparateurRangementError("Batch limité à 5 produits.")
                    product = create_preparateur_unknown_product_from_pack(
                        request=request,
                        form=unknown_product_form,
                        receive_initial_stock=False,
                    )
                    add_created_product_to_preparateur_rangement_batch(
                        request,
                        product=product,
                        quantity=unknown_product_form.cleaned_data["initial_quantity"],
                        mode=PREPARATEUR_RANGEMENT_MODE_RECEIPT,
                    )
                    messages.success(request, "Produit créé et ajouté au batch.")
                    unknown_product_form = ScanPackUnknownProductForm()
                    return _render_preparateur_rangement(
                        request,
                        unknown_product_form=unknown_product_form,
                    )
                except (PreparateurRangementError, StockError) as exc:
                    unknown_product_form.add_error(None, str(exc))
            return _render_preparateur_rangement(
                request,
                unknown_product_modal_open=True,
                unknown_product_form=unknown_product_form,
                unknown_product_source_code=request.POST.get("unknown_product_source_code", ""),
            )

        if action == "scan_product":
            product_code = (request.POST.get("product_code") or "").strip()
            mode = (request.POST.get("movement_mode") or "").strip()
            errors = []
            try:
                set_preparateur_rangement_mode(request, mode)
            except PreparateurRangementError as exc:
                errors.append(str(exc))
            try:
                quantity = _parse_rangement_quantity(request.POST.get("quantity"))
            except PreparateurRangementError as exc:
                errors.append(str(exc))
                quantity = None
            for error in errors:
                messages.error(request, error)
            if errors:
                return _render_preparateur_rangement(request)
            if not product_code:
                messages.error(request, "Code produit requis.")
                return _render_preparateur_rangement(request)

            product = resolve_preparateur_rangement_product(product_code)
            if product is None:
                if mode == PREPARATEUR_RANGEMENT_MODE_TRANSFER:
                    messages.error(
                        request,
                        "Impossible de déplacer un produit inconnu. Utilisez Entrée en stock.",
                    )
                    return _render_preparateur_rangement(request)
                messages.warning(request, "Produit inconnu. Terminer ou ajouter le produit.")
                return _render_preparateur_rangement(
                    request,
                    unknown_product_modal_open=True,
                    unknown_product_form=_build_unknown_product_form(
                        source_code=product_code,
                        quantity=quantity,
                    ),
                    unknown_product_source_code=product_code,
                )

            try:
                item = add_product_to_preparateur_rangement_batch(
                    request,
                    product=product,
                    quantity=quantity,
                    mode=mode,
                )
                if item.get("is_valid"):
                    messages.success(request, "Produit ajouté au batch rangement.")
                else:
                    messages.warning(request, item.get("stock_status_label"))
            except (PreparateurRangementError, StockError) as exc:
                messages.error(request, str(exc))
            return _render_preparateur_rangement(request)

    return _render_preparateur_rangement(request)
