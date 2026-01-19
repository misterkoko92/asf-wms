from .forms import ScanOrderCreateForm, ScanOrderLineForm, ScanOrderSelectForm
from .models import Order
from .order_scan_handlers import get_order_state


def build_order_scan_state(request, *, action):
    orders_qs = Order.objects.select_related("shipment").order_by("reference", "id")[:50]
    select_form = ScanOrderSelectForm(
        request.POST if action == "select_order" else None, orders_qs=orders_qs
    )
    create_form = ScanOrderCreateForm(
        request.POST if action == "create_order" else None
    )

    order_id = request.GET.get("order") or request.POST.get("order_id")
    selected_order = (
        Order.objects.select_related("shipment").filter(id=order_id).first()
        if order_id
        else None
    )

    line_form = ScanOrderLineForm(
        request.POST if action == "add_line" else None,
        initial={"order_id": selected_order.id} if selected_order else None,
    )
    order_lines, remaining_total = get_order_state(selected_order)

    return {
        "select_form": select_form,
        "create_form": create_form,
        "line_form": line_form,
        "selected_order": selected_order,
        "order_lines": order_lines,
        "remaining_total": remaining_total,
    }
