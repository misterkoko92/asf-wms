import logging
import re

from django.contrib import messages
from django.db import IntegrityError, connection, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from .carton_status_events import set_carton_status
from .models import (
    TEMP_SHIPMENT_REFERENCE_PREFIX,
    Carton,
    CartonStatus,
    RecipientProductPreferenceStatus,
    Shipment,
    ShipmentPreferenceOverride,
    ShipmentPreferenceOverrideAction,
    ShipmentStatus,
)
from .order_helpers import resolve_linked_order_for_shipment
from .recipient_product_preferences import (
    list_recipient_refusal_conflicts_for_carton,
    list_recipient_refusal_conflicts_for_products,
    recipient_has_explicit_refused_preferences,
)
from .scan_helpers import build_product_label
from .scan_pack_helpers import build_forced_packing_bins, parse_forced_carton_count
from .services import StockError, pack_carton, pack_carton_from_reserved
from .shipment_dossier_activity import record_shipment_dossier_activity
from .shipment_helpers import (
    build_destination_label,
    parse_shipment_lines,
    shipment_correspondent_contact_for_destination,
    shipment_link_for_recipient_contact,
    shipment_shipper_from_contact,
)
from .shipment_party_snapshot import (
    apply_shipment_party_snapshot,
    build_shipment_party_snapshot_payload,
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
CREATE_PACK_ACTION = "create_pack"
TEMP_SHIPMENT_REFERENCE_RE = re.compile(r"^EXP-TEMP-(\d+)$")
TEMP_SHIPMENT_REFERENCE_MAX_RETRIES = 5
logger = logging.getLogger(__name__)


def _parse_carton_count(raw_value):
    try:
        return max(0, int(raw_value))
    except (TypeError, ValueError):
        return 0


def _get_carton_count(form, request):
    if form.is_valid():
        return _parse_carton_count(form.cleaned_data.get("carton_count", 0))
    return _parse_carton_count(request.POST.get("carton_count", 0))


def _get_carton_count_from_post(request):
    return _parse_carton_count(request.POST.get("carton_count", 0))


def _is_save_draft_action(request):
    return (request.POST.get("action") or "").strip() in {
        SAVE_DRAFT_ACTION,
        SAVE_DRAFT_PACK_ACTION,
    }


def _is_save_draft_pack_action(request):
    return (request.POST.get("action") or "").strip() == SAVE_DRAFT_PACK_ACTION


def _is_create_pack_action(request):
    return (request.POST.get("action") or "").strip() == CREATE_PACK_ACTION


def _parse_forced_carton_count_from_request(request):
    try:
        return parse_forced_carton_count(request.POST.get("forced_carton_count"))
    except ValueError as exc:
        raise StockError(str(exc)) from exc


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
    return resolve_linked_order_for_shipment(shipment)


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


def _request_actor(request):
    user = getattr(request, "user", None)
    if user is None or not hasattr(user, "_meta"):
        return None
    if hasattr(user, "is_authenticated") and not user.is_authenticated:
        return None
    return user


def _warn_forced_carton_count(request, *, forced_carton_count, auto_count):
    if not forced_carton_count:
        return
    if auto_count == forced_carton_count:
        return
    messages.warning(
        request,
        _("Nombre de colis forcé: %(forced)s au lieu de %(auto)s.")
        % {"forced": forced_carton_count, "auto": auto_count},
    )


def _product_entry_key(product):
    return getattr(product, "id", None) or product


def _product_entry_label(product, *, fallback=""):
    return getattr(product, "name", None) or fallback or str(product)


def _pack_product_line_items(
    *,
    request,
    shipment,
    product_line_items,
    forced_carton_count,
    recipient_organization,
    has_refused_preferences,
    actor,
    pack_product_entry,
):
    if not product_line_items:
        return
    forced_bins = None
    if forced_carton_count:
        forced_bins = build_forced_packing_bins(product_line_items, forced_carton_count)
        if forced_bins:
            _warn_forced_carton_count(
                request,
                forced_carton_count=len(forced_bins),
                auto_count=len(product_line_items),
            )
    packing_bins = forced_bins or [
        {
            "items": {
                _product_entry_key(item["product"]): {
                    "product": item["product"],
                    "quantity": item["quantity"],
                    "expires_on": item.get("expires_on"),
                    "line_item": item,
                }
            }
        }
        for item in product_line_items
    ]

    for bin_data in packing_bins:
        carton = None
        conflicts_by_product_id = {}
        for entry in bin_data["items"].values():
            line_item = entry.get("line_item") or {}
            recipient_refusal_conflicts = []
            if has_refused_preferences:
                recipient_refusal_conflicts = _validate_recipient_refusal_conflicts_for_product(
                    recipient_organization=recipient_organization,
                    product=entry["product"],
                    override_confirmed=line_item.get(
                        "recipient_preference_override_confirmed",
                        False,
                    ),
                )
            carton = pack_product_entry(
                entry=entry,
                carton=carton,
            )
            if recipient_refusal_conflicts:
                conflicts_by_product_id[_product_entry_key(entry["product"])] = (
                    recipient_refusal_conflicts
                )
        for conflicts in conflicts_by_product_id.values():
            _record_recipient_refusal_overrides(
                shipment=shipment,
                carton=carton,
                recipient_organization=recipient_organization,
                conflicts=conflicts,
                user=actor,
            )


def _resolve_recipient_organization_for_selection(
    *, shipper_contact, recipient_contact, destination
):
    if shipper_contact is None or recipient_contact is None or destination is None:
        return None
    shipper = shipment_shipper_from_contact(shipper_contact)
    if shipper is None:
        return None
    link = shipment_link_for_recipient_contact(
        shipper=shipper,
        recipient_contact=recipient_contact,
        destination=destination,
    )
    if link is None:
        return None
    return getattr(link, "recipient_organization", None)


def _format_recipient_conflict_product_labels(conflicts):
    return ", ".join(build_product_label(conflict.product, "") for conflict in conflicts)


def _build_recipient_refusal_carton_error(*, carton, conflicts):
    return ngettext(
        "Attention : le colis %(carton)s contient %(products)s. "
        "Le destinataire a indiqué ne pas vouloir ce produit. "
        "Voulez vous continuer ou choisir un autre colis ?",
        "Attention : le colis %(carton)s contient %(products)s. "
        "Le destinataire a indiqué ne pas vouloir ces produits. "
        "Voulez vous continuer ou choisir un autre colis ?",
        len(conflicts),
    ) % {
        "carton": carton.code,
        "products": _format_recipient_conflict_product_labels(conflicts),
    }


def _build_recipient_refusal_product_error(*, conflicts):
    return ngettext(
        "Attention : le destinataire a indiqué ne pas vouloir %(products)s. "
        "Voulez vous continuer ou modifier la ligne ?",
        "Attention : le destinataire a indiqué ne pas vouloir %(products)s. "
        "Voulez vous continuer ou modifier la ligne ?",
        len(conflicts),
    ) % {
        "products": _format_recipient_conflict_product_labels(conflicts),
    }


def _existing_refusal_override_product_ids(*, shipment, recipient_organization, carton):
    return set(
        ShipmentPreferenceOverride.objects.filter(
            shipment=shipment,
            carton=carton,
            recipient_organization=recipient_organization,
            action=ShipmentPreferenceOverrideAction.OVERRIDE_REFUSAL,
        ).values_list("product_id", flat=True)
    )


def _validate_recipient_refusal_conflicts_for_carton(
    *,
    shipment,
    carton,
    recipient_organization,
    override_confirmed,
):
    if recipient_organization is None:
        return []
    conflicts = list_recipient_refusal_conflicts_for_carton(
        recipient_organization=recipient_organization,
        carton=carton,
    )
    if not conflicts:
        return []
    existing_product_ids = _existing_refusal_override_product_ids(
        shipment=shipment,
        recipient_organization=recipient_organization,
        carton=carton,
    )
    pending_conflicts = [
        conflict for conflict in conflicts if conflict.product.pk not in existing_product_ids
    ]
    if pending_conflicts and not override_confirmed:
        raise StockError(
            _build_recipient_refusal_carton_error(
                carton=carton,
                conflicts=pending_conflicts,
            )
        )
    return pending_conflicts


def _validate_recipient_refusal_conflicts_for_product(
    *,
    recipient_organization,
    product,
    override_confirmed,
):
    if recipient_organization is None:
        return []
    conflicts = list_recipient_refusal_conflicts_for_products(
        recipient_organization=recipient_organization,
        products=[product],
    )
    if conflicts and not override_confirmed:
        raise StockError(_build_recipient_refusal_product_error(conflicts=conflicts))
    return conflicts


def _record_recipient_refusal_overrides(
    *,
    shipment,
    carton,
    recipient_organization,
    conflicts,
    user,
):
    for conflict in conflicts:
        ShipmentPreferenceOverride.objects.create(
            shipment=shipment,
            carton=carton,
            recipient_organization=recipient_organization,
            product=conflict.product,
            preference_status_snapshot=RecipientProductPreferenceStatus.REFUSED,
            action=ShipmentPreferenceOverrideAction.OVERRIDE_REFUSAL,
            created_by=user,
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
        party_payload = build_shipment_party_snapshot_payload(
            shipper_contact=shipper_contact,
            recipient_contact=recipient_contact,
            correspondent_contact=correspondent_contact,
            shipper_name=shipper_contact.name if shipper_contact else "",
            recipient_name=recipient_contact.name if recipient_contact else "",
            correspondent_name=correspondent_contact.name if correspondent_contact else "",
        )
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
                    **party_payload,
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

    create_pack = _is_create_pack_action(request)
    carton_count = 0 if create_pack else _get_carton_count(form, request)
    try:
        forced_carton_count = (
            None if create_pack else _parse_forced_carton_count_from_request(request)
        )
    except StockError as exc:
        forced_carton_count = None
        form.add_error(None, str(exc))
    if carton_count > 0:
        line_values, line_items, line_errors = parse_shipment_lines(
            carton_count=carton_count,
            data=request.POST,
            allowed_carton_ids=available_carton_ids,
        )
    else:
        line_values, line_items, line_errors = [], [], {}
    response = None
    if form.is_valid() and not line_errors and not form.errors:
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
                recipient_organization = _resolve_recipient_organization_for_selection(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    destination=destination,
                )
                has_refused_preferences = bool(
                    recipient_organization
                    and recipient_has_explicit_refused_preferences(
                        recipient_organization=recipient_organization
                    )
                )
                actor = _request_actor(request)
                destination_label = build_destination_label(destination)
                party_payload = build_shipment_party_snapshot_payload(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    correspondent_contact=correspondent_contact,
                    shipper_name=shipper_contact.name,
                    recipient_name=recipient_contact.name,
                    correspondent_name=correspondent_contact.name,
                )
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
                    **party_payload,
                )
                if not create_pack:
                    product_line_items = [item for item in line_items if "product" in item]
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
                            recipient_refusal_conflicts = []
                            if has_refused_preferences:
                                recipient_refusal_conflicts = (
                                    _validate_recipient_refusal_conflicts_for_carton(
                                        shipment=shipment,
                                        carton=carton,
                                        recipient_organization=recipient_organization,
                                        override_confirmed=item.get(
                                            "recipient_preference_override_confirmed",
                                            False,
                                        ),
                                    )
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
                            _record_recipient_refusal_overrides(
                                shipment=shipment,
                                carton=carton,
                                recipient_organization=recipient_organization,
                                conflicts=recipient_refusal_conflicts,
                                user=actor,
                            )
                    _pack_product_line_items(
                        request=request,
                        shipment=shipment,
                        product_line_items=product_line_items,
                        forced_carton_count=forced_carton_count,
                        recipient_organization=recipient_organization,
                        has_refused_preferences=has_refused_preferences,
                        actor=actor,
                        pack_product_entry=lambda *, entry, carton: pack_carton(
                            user=request.user,
                            product=entry["product"],
                            quantity=entry["quantity"],
                            carton=carton,
                            carton_code=None,
                            shipment=shipment,
                            display_expires_on=entry.get("expires_on"),
                        ),
                    )
            sync_shipment_ready_state(shipment)
            messages.success(
                request,
                _("Expédition créée: %(reference)s.") % {"reference": shipment.reference},
            )
            if create_pack:
                response = redirect(_build_pack_redirect_url(shipment_reference=shipment.reference))
            else:
                response = redirect("scan:scan_shipment_edit", shipment.id)
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
    try:
        forced_carton_count = _parse_forced_carton_count_from_request(request)
    except StockError as exc:
        forced_carton_count = None
        form.add_error(None, str(exc))
    line_values, line_items, line_errors = parse_shipment_lines(
        carton_count=carton_count,
        data=request.POST,
        allowed_carton_ids=allowed_carton_ids,
    )
    response = None
    if form.is_valid() and not line_errors and not form.errors:
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
                recipient_organization = _resolve_recipient_organization_for_selection(
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    destination=destination,
                )
                has_refused_preferences = bool(
                    recipient_organization
                    and recipient_has_explicit_refused_preferences(
                        recipient_organization=recipient_organization
                    )
                )
                actor = _request_actor(request)
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
                apply_shipment_party_snapshot(
                    shipment,
                    shipper_contact=shipper_contact,
                    recipient_contact=recipient_contact,
                    correspondent_contact=correspondent_contact,
                    shipper_name=shipper_contact.name,
                    recipient_name=recipient_contact.name,
                    correspondent_name=correspondent_contact.name,
                )
                record_shipment_dossier_activity(
                    shipment=shipment,
                    label="Dossier modifié",
                    save=False,
                )
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
                        "party_snapshot",
                        "dossier_last_activity_at",
                        "dossier_last_activity_label",
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
                product_line_items = [item for item in line_items if "product" in item]
                if related_order is not None:
                    requested_quantities_by_product_id = {}
                    requested_product_labels = {}
                    for item in product_line_items:
                        product_id = item["product"].id
                        requested_quantities_by_product_id[product_id] = (
                            requested_quantities_by_product_id.get(product_id, 0) + item["quantity"]
                        )
                        requested_product_labels[product_id] = _product_entry_label(item["product"])
                    for (
                        product_id,
                        requested_quantity,
                    ) in requested_quantities_by_product_id.items():
                        order_line = order_lines_by_product.get(product_id)
                        if order_line is None:
                            raise StockError(_("Produit non présent dans la commande liée."))
                        if requested_quantity > order_line.remaining_quantity:
                            product_label = _product_entry_label(
                                getattr(order_line, "product", None),
                                fallback=requested_product_labels.get(product_id, ""),
                            )
                            raise StockError(
                                _(
                                    "%(product)s: quantité demandée supérieure au reliquat de la commande."
                                )
                                % {"product": product_label}
                            )
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
                    recipient_refusal_conflicts = []
                    if has_refused_preferences:
                        recipient_refusal_conflicts = (
                            _validate_recipient_refusal_conflicts_for_carton(
                                shipment=shipment,
                                carton=carton,
                                recipient_organization=recipient_organization,
                                override_confirmed=carton_item.get(
                                    "recipient_preference_override_confirmed",
                                    False,
                                ),
                            )
                        )
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
                    _record_recipient_refusal_overrides(
                        shipment=shipment,
                        carton=carton,
                        recipient_organization=recipient_organization,
                        conflicts=recipient_refusal_conflicts,
                        user=actor,
                    )

                _pack_product_line_items(
                    request=request,
                    shipment=shipment,
                    product_line_items=product_line_items,
                    forced_carton_count=forced_carton_count,
                    recipient_organization=recipient_organization,
                    has_refused_preferences=has_refused_preferences,
                    actor=actor,
                    pack_product_entry=lambda *, entry, carton: (
                        pack_carton_from_reserved(
                            user=request.user,
                            line=order_lines_by_product[entry["product"].id],
                            quantity=entry["quantity"],
                            carton=carton,
                            shipment=shipment,
                            display_expires_on=entry.get("expires_on"),
                        )
                        if related_order is not None
                        else pack_carton(
                            user=request.user,
                            product=entry["product"],
                            quantity=entry["quantity"],
                            carton=carton,
                            carton_code=None,
                            shipment=shipment,
                            display_expires_on=entry.get("expires_on"),
                        )
                    ),
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
