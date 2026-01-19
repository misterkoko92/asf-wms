from .forms import ScanReceiptPalletForm
from .pallet_listing import (
    PALLET_LISTING_MAPPING_FIELDS,
    PALLET_LOCATION_FIELDS,
    PALLET_REVIEW_FIELDS,
)
from .pallet_listing_handlers import (
    handle_pallet_listing_action,
    hydrate_listing_state_from_pending,
    init_listing_state,
)
from .receipt_pallet_handlers import handle_pallet_create_post


def build_receive_pallet_state(request, *, action):
    create_form = ScanReceiptPalletForm(
        request.POST
        if request.method == "POST" and action in ("", "pallet_create")
        else None
    )
    listing_form = ScanReceiptPalletForm(
        request.POST if action == "listing_upload" else None,
        prefix="listing",
    )
    listing_state = init_listing_state()
    response = None
    if request.method == "POST":
        response = handle_pallet_listing_action(
            request,
            action=action,
            listing_form=listing_form,
            state=listing_state,
        )
    if (
        response is None
        and request.method == "POST"
        and action in ("", "pallet_create")
        and create_form.is_valid()
    ):
        response = handle_pallet_create_post(request, form=create_form)

    pending = request.session.get("pallet_listing_pending")
    listing_meta = hydrate_listing_state_from_pending(listing_state, pending)

    return {
        "response": response,
        "create_form": create_form,
        "listing_form": listing_form,
        "listing_state": listing_state,
        "listing_meta": listing_meta,
        "pending": pending,
    }


def build_receive_pallet_context(state):
    listing_state = state["listing_state"]
    pending = state["pending"]
    return {
        "active": "receive_pallet",
        "create_form": state["create_form"],
        "listing_form": state["listing_form"],
        "listing_stage": listing_state["listing_stage"],
        "listing_columns": listing_state["listing_columns"],
        "listing_rows": listing_state["listing_rows"],
        "listing_errors": listing_state["listing_errors"],
        "listing_token": pending.get("token") if pending else "",
        "listing_meta": state["listing_meta"],
        "mapping_fields": PALLET_LISTING_MAPPING_FIELDS,
        "review_fields": PALLET_REVIEW_FIELDS,
        "location_fields": PALLET_LOCATION_FIELDS,
        "listing_sheet_names": listing_state["listing_sheet_names"],
        "listing_sheet_name": listing_state["listing_sheet_name"],
        "listing_header_row": listing_state["listing_header_row"],
        "listing_pdf_pages_mode": listing_state["listing_pdf_pages_mode"],
        "listing_pdf_page_start": listing_state["listing_pdf_page_start"],
        "listing_pdf_page_end": listing_state["listing_pdf_page_end"],
        "listing_pdf_total_pages": listing_state["listing_pdf_total_pages"],
        "listing_file_type": listing_state["listing_file_type"],
    }
