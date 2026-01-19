from django.shortcuts import redirect

from .models import Carton, CartonStatus


def handle_carton_status_update(request):
    if request.method != "POST" or request.POST.get("action") != "update_carton_status":
        return None
    carton_id = request.POST.get("carton_id")
    carton = Carton.objects.filter(pk=carton_id).select_related("shipment").first()
    status_value = (request.POST.get("status") or "").strip()
    allowed = {
        CartonStatus.DRAFT,
        CartonStatus.PICKING,
        CartonStatus.PACKED,
    }
    if (
        carton
        and carton.status != CartonStatus.SHIPPED
        and status_value in allowed
        and carton.shipment_id is None
    ):
        if carton.status != status_value:
            carton.status = status_value
            carton.save(update_fields=["status"])
    return redirect("scan:scan_cartons_ready")
