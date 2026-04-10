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


def build_receive_listing_state(request, *, action):
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

    pending = request.session.get("pallet_listing_pending")
    listing_meta = hydrate_listing_state_from_pending(listing_state, pending)

    return {
        "response": response,
        "listing_form": listing_form,
        "listing_state": listing_state,
        "listing_meta": listing_meta,
        "pending": pending,
    }


def build_receive_listing_context(state):
    listing_state = state["listing_state"]
    pending = state["pending"]
    return {
        "active": "receive_listing",
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
