from .forms import ScanReceiptPalletForm
from .receipt_pallet_handlers import handle_pallet_create_post


def build_receive_pallet_state(request, *, action):
    create_form = ScanReceiptPalletForm(
        request.POST if request.method == "POST" and action in ("", "pallet_create") else None
    )
    response = None
    if request.method == "POST" and action in ("", "pallet_create") and create_form.is_valid():
        response = handle_pallet_create_post(request, form=create_form)

    return {
        "response": response,
        "create_form": create_form,
    }


def build_receive_pallet_context(state):
    return {
        "active": "receive_pallet",
        "create_form": state["create_form"],
    }
