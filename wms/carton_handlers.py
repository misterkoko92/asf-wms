from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import gettext as _

from .carton_status_events import set_carton_status
from .models import Carton, CartonStatus, Shipment, ShipmentStatus
from .services import StockError, unpack_carton
from .shipment_status import sync_shipment_ready_state

LOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}

MUTATION_BLOCKED_SHIPMENT_STATUSES = {
    ShipmentStatus.PLANNED,
    ShipmentStatus.SHIPPED,
    ShipmentStatus.RECEIVED_CORRESPONDENT,
    ShipmentStatus.DELIVERED,
}
ASSIGNABLE_SHIPMENT_STATUSES = {
    ShipmentStatus.DRAFT,
    ShipmentStatus.PICKING,
    ShipmentStatus.PACKED,
}


def _shipment_is_locked(carton):
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return False
    if shipment.status in LOCKED_SHIPMENT_STATUSES:
        return True
    return bool(getattr(shipment, "is_disputed", False))


def _carton_can_be_mutated(carton):
    if not carton or carton.status == CartonStatus.SHIPPED:
        return False
    shipment = getattr(carton, "shipment", None)
    if not shipment:
        return True
    if getattr(shipment, "is_disputed", False):
        return False
    return shipment.status not in MUTATION_BLOCKED_SHIPMENT_STATUSES


def _shipment_can_receive_cartons(shipment):
    if not shipment:
        return False
    if getattr(shipment, "is_disputed", False):
        return False
    return shipment.status in ASSIGNABLE_SHIPMENT_STATUSES


def _set_bulk_carton_status(carton, *, new_status, reason, user, update_fields=None):
    set_carton_status(
        carton=carton,
        new_status=new_status,
        reason=reason,
        user=user,
        update_fields=update_fields,
    )


def _bulk_status_feedback(request, *, action, updated_count, ignored_count):
    if not hasattr(request, "_messages"):
        return
    action_labels = {
        "bulk_update_cartons_picking": _("mis en préparation"),
        "bulk_update_cartons_packed": _("mis en prêt"),
        "bulk_mark_cartons_labeled": _("marqués étiquetés"),
        "bulk_mark_cartons_assigned": _("repassés en affecté"),
        "bulk_assign_cartons_shipment": _("affectés à l'expédition"),
    }
    if updated_count:
        message = _("%(count)s colis %(action_label)s.") % {
            "count": updated_count,
            "action_label": action_labels.get(action, _("mis à jour")),
        }
        if ignored_count:
            message += " " + _("%(count)s ignoré(s).") % {"count": ignored_count}
        messages.success(request, message)
        return
    messages.warning(request, _("Aucun colis sélectionné n'a pu être mis à jour."))


def handle_carton_status_update(request):
    if request.method != "POST":
        return None
    action = (request.POST.get("action") or request.POST.get("bulk_action") or "").strip()
    if (
        not action
        and (request.POST.get("bulk_shipment_id") or "").strip()
        and request.POST.getlist("selected_carton_ids")
    ):
        action = "bulk_assign_cartons_shipment"
    allowed_actions = {
        "update_carton_status",
        "mark_carton_labeled",
        "mark_carton_assigned",
        "delete_carton",
        "bulk_update_cartons_picking",
        "bulk_update_cartons_packed",
        "bulk_mark_cartons_labeled",
        "bulk_mark_cartons_assigned",
        "bulk_assign_cartons_shipment",
    }
    if action not in allowed_actions:
        return None
    carton_id = request.POST.get("carton_id")
    carton = Carton.objects.filter(pk=carton_id).select_related("shipment").first()
    status_value = (request.POST.get("status") or "").strip()
    allowed = {
        CartonStatus.DRAFT,
        CartonStatus.PICKING,
        CartonStatus.PACKED,
    }
    if action == "update_carton_status":
        if (
            carton
            and carton.status != CartonStatus.SHIPPED
            and status_value in allowed
            and carton.shipment_id is None
        ):
            set_carton_status(
                carton=carton,
                new_status=status_value,
                reason="manual_update",
                user=getattr(request, "user", None),
            )
        return redirect("scan:scan_cartons_ready")

    if action == "delete_carton":
        if not _carton_can_be_mutated(carton):
            return redirect("scan:scan_cartons_ready")
        shipment = carton.shipment
        try:
            with transaction.atomic():
                if carton.cartonitem_set.exists():
                    unpack_carton(
                        user=getattr(request, "user", None),
                        carton=carton,
                    )
                carton.delete()
        except StockError:
            return redirect("scan:scan_cartons_ready")
        if shipment is not None:
            sync_shipment_ready_state(shipment)
        return redirect("scan:scan_cartons_ready")

    if action in {
        "bulk_update_cartons_picking",
        "bulk_update_cartons_packed",
        "bulk_mark_cartons_labeled",
        "bulk_mark_cartons_assigned",
        "bulk_assign_cartons_shipment",
    }:
        cartons = list(
            Carton.objects.filter(pk__in=request.POST.getlist("selected_carton_ids"))
            .select_related("shipment")
            .order_by("id")
        )
        target_shipment = None
        if action == "bulk_assign_cartons_shipment":
            target_shipment = (
                Shipment.objects.filter(pk=request.POST.get("bulk_shipment_id"))
                .select_related("destination")
                .first()
            )
            if not _shipment_can_receive_cartons(target_shipment):
                _bulk_status_feedback(
                    request,
                    action=action,
                    updated_count=0,
                    ignored_count=len(cartons),
                )
                return redirect("scan:scan_cartons_ready")
        touched_shipments = set()
        updated_count = 0
        for selected_carton in cartons:
            if action == "bulk_assign_cartons_shipment":
                if selected_carton.shipment_id or not _carton_can_be_mutated(selected_carton):
                    continue
                selected_carton.shipment = target_shipment
                selected_carton.preassigned_destination = None
                _set_bulk_carton_status(
                    selected_carton,
                    new_status=CartonStatus.ASSIGNED,
                    reason="bulk_assign_shipment",
                    user=getattr(request, "user", None),
                    update_fields=["shipment", "preassigned_destination"],
                )
                touched_shipments.add(target_shipment.id)
                updated_count += 1
                continue
            if action == "bulk_update_cartons_picking":
                if selected_carton.shipment_id or not _carton_can_be_mutated(selected_carton):
                    continue
                if selected_carton.status == CartonStatus.PICKING:
                    continue
                _set_bulk_carton_status(
                    selected_carton,
                    new_status=CartonStatus.PICKING,
                    reason="manual_update",
                    user=getattr(request, "user", None),
                )
                updated_count += 1
                continue
            if action == "bulk_update_cartons_packed":
                if selected_carton.shipment_id or not _carton_can_be_mutated(selected_carton):
                    continue
                if selected_carton.status == CartonStatus.PACKED:
                    continue
                _set_bulk_carton_status(
                    selected_carton,
                    new_status=CartonStatus.PACKED,
                    reason="manual_update",
                    user=getattr(request, "user", None),
                )
                updated_count += 1
                continue
            if not selected_carton.shipment_id or _shipment_is_locked(selected_carton):
                continue
            if action == "bulk_mark_cartons_labeled" and selected_carton.status in {
                CartonStatus.ASSIGNED,
                CartonStatus.PACKED,
            }:
                _set_bulk_carton_status(
                    selected_carton,
                    new_status=CartonStatus.LABELED,
                    reason="mark_labeled",
                    user=getattr(request, "user", None),
                )
                touched_shipments.add(selected_carton.shipment_id)
                updated_count += 1
            if (
                action == "bulk_mark_cartons_assigned"
                and selected_carton.status == CartonStatus.LABELED
            ):
                _set_bulk_carton_status(
                    selected_carton,
                    new_status=CartonStatus.ASSIGNED,
                    reason="mark_assigned",
                    user=getattr(request, "user", None),
                )
                touched_shipments.add(selected_carton.shipment_id)
                updated_count += 1
        if touched_shipments:
            for shipment in Shipment.objects.filter(pk__in=touched_shipments):
                sync_shipment_ready_state(shipment)
        _bulk_status_feedback(
            request,
            action=action,
            updated_count=updated_count,
            ignored_count=max(len(cartons) - updated_count, 0),
        )
        return redirect("scan:scan_cartons_ready")

    if not carton or not carton.shipment_id or _shipment_is_locked(carton):
        return redirect("scan:scan_cartons_ready")

    shipment = carton.shipment
    if action == "mark_carton_labeled":
        if carton.status in {CartonStatus.ASSIGNED, CartonStatus.PACKED}:
            set_carton_status(
                carton=carton,
                new_status=CartonStatus.LABELED,
                reason="mark_labeled",
                user=getattr(request, "user", None),
            )
            sync_shipment_ready_state(shipment)
        return redirect("scan:scan_cartons_ready")

    if action == "mark_carton_assigned":
        if carton.status == CartonStatus.LABELED:
            set_carton_status(
                carton=carton,
                new_status=CartonStatus.ASSIGNED,
                reason="mark_assigned",
                user=getattr(request, "user", None),
            )
            sync_shipment_ready_state(shipment)
    return redirect("scan:scan_cartons_ready")
