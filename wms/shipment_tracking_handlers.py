from django.contrib import messages
from django.shortcuts import redirect

from .models import ShipmentTrackingEvent


def handle_shipment_tracking_post(request, *, shipment, form):
    if request.method != "POST" or not form.is_valid():
        return None
    ShipmentTrackingEvent.objects.create(
        shipment=shipment,
        status=form.cleaned_data["status"],
        actor_name=form.cleaned_data["actor_name"],
        actor_structure=form.cleaned_data["actor_structure"],
        comments=form.cleaned_data["comments"] or "",
        created_by=request.user if request.user.is_authenticated else None,
    )
    messages.success(request, "Suivi mis à jour.")
    return redirect("scan:scan_shipment_track", tracking_token=shipment.tracking_token)
