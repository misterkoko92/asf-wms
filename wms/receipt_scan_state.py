from .forms import ScanReceiptCreateForm, ScanReceiptLineForm, ScanReceiptSelectForm
from .models import Receipt
from .receipt_handlers import get_receipt_lines_state


def build_receipt_scan_state(request, *, action):
    receipts_qs = Receipt.objects.select_related("warehouse").order_by(
        "reference", "id"
    )[:50]
    select_form = ScanReceiptSelectForm(
        request.POST if action == "select_receipt" else None, receipts_qs=receipts_qs
    )
    create_form = ScanReceiptCreateForm(
        request.POST if action == "create_receipt" else None
    )

    receipt_id = request.GET.get("receipt") or request.POST.get("receipt_id")
    selected_receipt = Receipt.objects.filter(id=receipt_id).first() if receipt_id else None

    line_form = ScanReceiptLineForm(
        request.POST if action == "add_line" else None,
        initial={"receipt_id": selected_receipt.id} if selected_receipt else None,
    )
    receipt_lines, pending_count = get_receipt_lines_state(selected_receipt)

    return {
        "select_form": select_form,
        "create_form": create_form,
        "line_form": line_form,
        "selected_receipt": selected_receipt,
        "receipt_lines": receipt_lines,
        "pending_count": pending_count,
    }
