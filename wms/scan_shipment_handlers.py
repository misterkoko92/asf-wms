import logging
import re

from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _

from .carton_status_events import set_carton_status
from .models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    Carton,
    CartonStatus,
    Shipment,
    ShipmentStatus,
)
from .services import StockError, pack_carton, pack_carton_from_reserved
from .shipment_helpers import (
    build_destination_label,
    parse_shipment_lines,
    shipment_correspondent_contact_for_destination,
    shipment_link_for_recipient_contact,
    shipment_shipper_from_contact,
)
from .shipment_status import sync_shipment_ready_state

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
SAVE_DRAFT_ACTION = "save_draft"
SAVE_DRAFT_PACK_ACTION = "save_draft_pack"
TEMP_SHIPMENT_REFERENCE_RE = re.compile(r"^EXP-TEMP-(\d+)$")
TEMP_SHIPMENT_REFERENCE_MAX_RETRIES = 5
logger = logging.getLogger(__name__)


def _parse_carton_count(raw_value):
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return 1


def _get_carton_count(form, request):
    if form.is_valid():
        return form.cleaned_data["carton_count"]
    return _parse_carton_count(request.POST.get("carton_count", 1))


def _get_carton_count_from_post(request):
    return _parse_carton_count(request.POST.get("carton_count", 1))


def _is_save_draft_action(request):
    return (request.POST.get("action") or "").strip() in {
        SAVE_DRAFT_ACTION,
        SAVE_DRAFT_PACK_ACTION,
    }


def _is_save_draft_pack_action(request):
    return (request.POST.get("action") or "").strip() == SAVE_DRAFT_PACK_ACTION


def _next_temp_shipment_reference():
    max_number = 0
    references = Shipment.objects.filter(
        reference__startswith=TEMP_SHIPMENT_REFERENCE_PREFIX
    ).values_list("reference", flat=True)
    for reference in references:
        match = TEMP_SHIPMENT_REFERENCE_RE.match(reference or "")
        if not match:
            continue
        max_number = max(max_number, int(match.group(1)))
    return f"{TEMP_SHIPMENT_REFERENCE_PREFIX}{max_number + 1:02d}"


def _resolve_optional_contact(form, field_name):
    raw_value = (form.data.get(field_name) or "").strip()
    if not raw_value:
        return None, None
    field = form.fields.get(field_name)
    if field is None:
        return raw_value, None
    contact = field.queryset.filter(pk=raw_value).first()
    return raw_value, contact


def _build_pack_redirect_url(*, shipment_reference):
    base_url = reverse("scan:scan_pack")
    return f"{base_url}?shipment_reference={shipment_reference}"


def _related_order_for_shipment(shipment):
    try:
        return shipment.order
    except AttributeError:
        return None
    except Shipment.order.RelatedObjectDoesNotExist:
        return None


def _validate_shipment_party_selection(*, shipper_contact, recipient_contact, destination):
    shipper = None
    if shipper_contact is not None:
        shipper = shipment_shipper_from_contact(shipper_contact)
        if shipper is None:
            raise StockError(_("Expéditeur non disponible pour cette destination."))
    if recipient_contact is not None:
        if shipper is None:
            raise StockError(_("Destinataire non disponible pour cet expéditeur."))
        if (
            shipment_link_for_recipient_contact(
                shipper=shipper,
                recipient_contact=recipient_contact,
                destination=destination,
            )
            is None
        ):
            raise StockError(_("Destinataire non disponible pour cet expéditeur."))

    correspondent_contact = shipment_correspondent_contact_for_destination(destination)
    if destination is not None and correspondent_contact is None:
        raise StockError(_("Contact non disponible pour cette destination."))
    return correspondent_contact


def _build_preassigned_destination_mismatch_error(*, carton, destination):
    preassigned_destination = getattr(carton, "preassigned_destination", None)
    expected_label = (
        getattr(preassigned_destination, "iata_code", "") or ""
    ).strip() or build_destination_label(preassigned_destination)
    current_label = (
        getattr(destination, "iata_code", "") or ""
    ).strip() or build_destination_label(destination)
    return _(
        "Ce colis est déjà affecté pour %(expected)s. "
        "Souhaitez vous vraiment l'affecter à cette expédition pour %(current)s ?"
    ) % {
        "expected": expected_label,
        "current": current_label,
    }


def _validate_carton_preassignment(*, carton, destination, mismatch_confirmed):
    destination_id = getattr(destination, "id", None)
    preassigned_destination_id = getattr(carton, "preassigned_destination_id", None)
    if not preassigned_destination_id or not destination_id:
        return
    if preassigned_destination_id == destination_id or mismatch_confirmed:
        return
    raise StockError(
        _build_preassigned_destination_mismatch_error(carton=carton, destination=destination)
    )


def _handle_shipment_save_draft_post(request, *, form, redirect_to_pack=False):
    destination_value = (form.data.get("destination") or "").strip()
    if not destination_value:
        form.add_error(
            "destination",
            _("Merci de sélectionner une destination avant d'enregistrer un brouillon."),
        )
        return None

    destination_field = form.fields.get("destination")
    destination = (
        destination_field.queryset.filter(pk=destination_value).first()
        if destination_field is not None
        else None
    )
    if destination is None:
        form.add_error("destination", _("Destination invalide."))
        return None

    shipper_value, shipper_contact = _resolve_optional_contact(form, "shipper_contact")
    recipient_value, recipient_contact = _resolve_optional_contact(form, "recipient_contact")
    if shipper_value and shipper_contact is None:
        form.add_error("shipper_contact", _("Contact non disponible pour cette destination."))
        return None
    if recipient_value and recipient_contact is None:
        form.add_error(
            "recipient_contact",
            _("Destinataire non disponible pour cet expéditeur."),
        )
        return None

    try:
        correspondent_contact = _validate_shipment_party_selection(
            shipper_contact=shipper_contact,
            recipient_contact=recipient_contact,
            destination=destination,
        )
    except StockError as exc:
        form.add_error(None, str(exc))
        return None

    destination_label = build_destination_label(destination)
    last_error = None
    for _attempt in range(TEMP_SHIPMENT_REFERENCE_MAX_RETRIES):
        draft_reference = _next_temp_shipment_reference()
        try:
            with transaction.atomic():
                shipment = Shipment.objects.create(
                    reference=draft_reference,
                    status=ShipmentStatus.DRAFT,
                    shipper_name=shipper_contact.name if shipper_contact else "",
                    shipper_contact_ref=shipper_contact,
                    recipient_name=recipient_contact.name if recipient_contact else "",
                    recipient_contact_ref=recipient_contact,
                    correspondent_name=correspondent_contact.name if correspondent_contact else "",
                    correspondent_contact_ref=correspondent_contact,
                    destination=destination,
                    destination_address=destination_label,
                    destination_country=destination.country,
                    created_by=request.user,
                )
        except IntegrityError as exc:
            last_error = exc
            continue

        messages.success(
            request,
            _("Brouillon enregistré: %(reference)s.") % {"reference": shipment.reference},
        )
        if redirect_to_pack:
            return redirect(_build_pack_redirect_url(shipment_reference=shipment.reference))
        return redirect("scan:scan_shipment_edit", shipment.id)

    raise StockError(_("Impossible de générer une référence de brouillon unique.")) from last_error


def handle_shipment_create_post(request, *, form, available_carton_ids):
    if _is_save_draft_action(request):
        carton_count = _get_carton_count_from_post(request)
        line_values, _line_items, _ignored_line_errors = parse_shipment_lines(
            carton_count=carton_count,
            data=request.POST,
            allowed_carton_ids=available_carton_ids,
        )
        response = _handle_shipment_save_draft_post(
            request,
            form=form,
            redirect_to_pack=_is_save_draft_pack_action(request),
        )
        return response, carton_count, line_values, {}

    carton_count = _get_carton_count(form, request)
    line_values, line_items, line_errors = parse_shipment_lines(
        carton_count=carton_count,
        data=request.POST,
        allowed_carton_ids=available_carton_ids,
    )
    response = None
    if form.is_valid() and not line_errors:
        try:
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = _validate_shipment_party_selection(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    destination=destination,
                )
                destination_label = build_destination_label(destination)
                shipment = Shipment.objects.create(
                    status=ShipmentStatus.DRAFT,
                    shipper_name=shipper_contact.name,
                    shipper_contact_ref=shipper_contact,
                    recipient_name=recipient_contact.name,
                    recipient_contact_ref=recipient_contact,
                    correspondent_name=correspondent_contact.name,
                    correspondent_contact_ref=correspondent_contact,
                    destination=destination,
                    destination_address=destination_label,
                    destination_country=destination.country,
                    created_by=request.user,
                )
                for item in line_items:
                    carton_id = item.get("carton_id")
                    if carton_id:
                        carton_query = Carton.objects.filter(
                            id=carton_id,
                            status=CartonStatus.PACKED,
                            shipment__isnull=True,
                        ).select_related("preassigned_destination")
                        if connection.features.has_select_for_update:
                            carton_query = carton_query.select_for_update()
                        carton = carton_query.first()
                        if carton is None:
                            raise StockError(_("Carton indisponible."))
                        _validate_carton_preassignment(
                            carton=carton,
                            destination=destination,
                            mismatch_confirmed=item.get(
                                "preassigned_destination_confirmed",
                                False,
                            ),
                        )
                        carton.shipment = shipment
                        carton.preassigned_destination = None
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            update_fields=["shipment", "preassigned_destination"],
                            reason="shipment_create_assign",
                            user=getattr(request, "user", None),
                        )
                    else:
                        carton = pack_carton(
                            user=request.user,
                            product=item["product"],
                            quantity=item["quantity"],
                            carton=None,
                            carton_code=None,
                            shipment=shipment,
                            display_expires_on=item.get("expires_on"),
                        )
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            reason="shipment_create_pack_assign",
                            user=getattr(request, "user", None),
                        )
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                _("Expédition créée: %(reference)s.") % {"reference": shipment.reference},
            )
            response = redirect("scan:scan_shipment_create")
        except StockError as exc:
            form.add_error(None, str(exc))
        except IntegrityError:
            logger.exception("Integrity error while creating shipment")
            form.add_error(
                None,
                _("Erreur technique lors de la création de l'expédition. Merci de réessayer."),
            )
    return response, carton_count, line_values, line_errors


def handle_shipment_edit_post(request, *, form, shipment, allowed_carton_ids):
    carton_count = _get_carton_count(form, request)
    line_values, line_items, line_errors = parse_shipment_lines(
        carton_count=carton_count,
        data=request.POST,
        allowed_carton_ids=allowed_carton_ids,
    )
    response = None
    if form.is_valid() and not line_errors:
        try:
            shipment_status = getattr(shipment, "status", ShipmentStatus.DRAFT)
            if shipment_status in LOCKED_SHIPMENT_STATUSES:
                raise StockError(_("Expédition verrouillée: modification des colis impossible."))
            if getattr(shipment, "is_disputed", False):
                raise StockError(_("Expédition en litige: modification des colis impossible."))
            with transaction.atomic():
                destination = form.cleaned_data["destination"]
                shipper_contact = form.cleaned_data["shipper_contact"]
                recipient_contact = form.cleaned_data["recipient_contact"]
                correspondent_contact = _validate_shipment_party_selection(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    destination=destination,
                )
                destination_label = build_destination_label(destination)

                shipment.destination = destination
                shipment.shipper_name = shipper_contact.name
                shipment.shipper_contact_ref = shipper_contact
                shipment.recipient_name = recipient_contact.name
                shipment.recipient_contact_ref = recipient_contact
                shipment.correspondent_name = correspondent_contact.name
                shipment.correspondent_contact_ref = correspondent_contact
                shipment.destination_address = destination_label
                shipment.destination_country = destination.country
                shipment.save(
                    update_fields=[
                        "destination",
                        "shipper_name",
                        "shipper_contact_ref",
                        "recipient_name",
                        "recipient_contact_ref",
                        "correspondent_name",
                        "correspondent_contact_ref",
                        "destination_address",
                        "destination_country",
                    ]
                )
                related_order = _related_order_for_shipment(shipment)
                order_lines_by_product = {}
                if related_order is not None:
                    order_lines_by_product = {
                        line.product_id: line
                        for line in related_order.lines.select_related("product").all()
                    }

                selected_carton_ids = {
                    item["carton_id"] for item in line_items if "carton_id" in item
                }
                carton_items_by_id = {
                    item["carton_id"]: item for item in line_items if "carton_id" in item
                }
                cartons_to_remove = shipment.carton_set.exclude(id__in=selected_carton_ids)
                for carton in cartons_to_remove:
                    if carton.status == CartonStatus.SHIPPED:
                        raise StockError(_("Impossible de retirer un carton expédié."))
                    carton.shipment = None
                    if carton.status in {CartonStatus.ASSIGNED, CartonStatus.LABELED}:
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.PACKED,
                            update_fields=["shipment"],
                            reason="shipment_edit_unassign",
                            user=getattr(request, "user", None),
                        )
                    else:
                        carton.save(update_fields=["shipment"])

                for carton_id in selected_carton_ids:
                    carton_item = carton_items_by_id.get(carton_id, {})
                    carton_query = Carton.objects.filter(id=carton_id).select_related(
                        "preassigned_destination"
                    )
                    if connection.features.has_select_for_update:
                        carton_query = carton_query.select_for_update()
                    carton = carton_query.first()
                    if carton is None:
                        raise StockError(_("Carton introuvable."))
                    if carton.shipment_id and carton.shipment_id != shipment.id:
                        raise StockError(_("Carton indisponible."))
                    if carton.shipment_id != shipment.id and carton.status != CartonStatus.PACKED:
                        raise StockError(_("Carton indisponible."))
                    if carton.shipment_id != shipment.id:
                        _validate_carton_preassignment(
                            carton=carton,
                            destination=destination,
                            mismatch_confirmed=carton_item.get(
                                "preassigned_destination_confirmed",
                                False,
                            ),
                        )
                        carton.shipment = shipment
                        carton.preassigned_destination = None
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            update_fields=["shipment", "preassigned_destination"],
                            reason="shipment_edit_assign_existing",
                            user=getattr(request, "user", None),
                        )
                    elif carton.status == CartonStatus.PACKED:
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            reason="shipment_edit_reassign",
                            user=getattr(request, "user", None),
                        )

                for item in line_items:
                    if "product" in item:
                        if related_order is not None:
                            order_line = order_lines_by_product.get(item["product"].id)
                            if order_line is None:
                                raise StockError(_("Produit non présent dans la commande liée."))
                            if item["quantity"] > order_line.remaining_quantity:
                                raise StockError(
                                    _(
                                        "%(product)s: quantité demandée supérieure au reliquat de la commande."
                                    )
                                    % {"product": item["product"].name}
                                )
                            carton = pack_carton_from_reserved(
                                user=request.user,
                                line=order_line,
                                quantity=item["quantity"],
                                carton=None,
                                shipment=shipment,
                                display_expires_on=item.get("expires_on"),
                            )
                        else:
                            carton = pack_carton(
                                user=request.user,
                                product=item["product"],
                                quantity=item["quantity"],
                                carton=None,
                                carton_code=None,
                                shipment=shipment,
                                display_expires_on=item.get("expires_on"),
                            )
                        set_carton_status(
                            carton=carton,
                            new_status=CartonStatus.ASSIGNED,
                            reason="shipment_edit_pack_assign",
                            user=getattr(request, "user", None),
                        )
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                _("Expédition mise à jour: %(reference)s.") % {"reference": shipment.reference},
            )
            response = redirect("scan:scan_shipments_ready")
        except StockError as exc:
            form.add_error(None, str(exc))
    return response, carton_count, line_values, line_errors
