from django.shortcuts import redirect

from .forms import ScanListingEntryForm
from .pallet_listing import (
    PALLET_LISTING_MAPPING_FIELDS,
    PALLET_LOCATION_FIELDS,
    PALLET_REVIEW_FIELDS,
    build_listing_columns,
    build_listing_review_state,
    build_listing_visible_columns,
    load_listing_table,
)
from .pallet_listing_handlers import (
    handle_pallet_listing_action,
    hydrate_listing_state_from_pending,
    init_listing_state,
)


def _entry_initial_from_pending(pending):
    pending = pending or {}
    return {
        "listing_entry_file_type": pending.get("entry_file_type") or pending.get("file_type") or "",
        "listing_entry_receipt_id": pending.get("receipt_id") or "",
    }


def _restore_listing_stage_from_pending(listing_state, pending):
    if not pending:
        return

    stage = (pending.get("stage") or "").strip()
    if not stage:
        if pending.get("pdf_analysis") and not pending.get("headers"):
            stage = "analysis"
        elif pending.get("headers") and pending.get("mapping"):
            stage = "mapping"
    if stage not in {"upload", "analysis", "mapping", "suggestions", "review"}:
        return

    listing_state["listing_stage"] = stage
    if stage in {"upload", "analysis"}:
        return

    try:
        headers, rows = load_listing_table(pending)
    except (OSError, ValueError):
        return

    mapping = pending.get("mapping") or {}
    if stage == "mapping":
        listing_state["listing_columns"] = build_listing_columns(headers, rows, mapping)
        return

    review_state = build_listing_review_state(
        rows,
        mapping,
        review_overrides=pending.get("review_overrides"),
        dismissed_suggestion_ids=pending.get("dismissed_suggestion_ids"),
    )
    listing_state["listing_rows"] = review_state["rows"]
    listing_state["listing_group_suggestions"] = review_state["group_suggestions"]


def _resolve_listing_focus_card_id(listing_state):
    stage = listing_state["listing_stage"]
    if stage == "review":
        return "scan-receive-pallet-review-card"
    if stage == "suggestions":
        return "scan-receive-listing-suggestions-card"
    if stage == "mapping":
        return "scan-receive-pallet-mapping-card"
    if stage == "analysis":
        return "scan-receive-listing-analysis-card"

    file_type = listing_state["listing_entry_file_type"]
    if file_type:
        return f"scan-receive-listing-{file_type}-card"
    return "scan-receive-listing-intake-card"


def build_receive_listing_state(request, *, action):
    pending = request.session.get("pallet_listing_pending")
    listing_state = init_listing_state()
    response = None

    if request.method == "POST" and action == "listing_configure":
        listing_entry_form = ScanListingEntryForm(request.POST)
    else:
        listing_entry_form = ScanListingEntryForm(
            initial=_entry_initial_from_pending(pending),
        )

    if request.method == "POST" and action == "listing_configure" and listing_entry_form.is_valid():
        updated_pending = dict(pending or {})
        updated_pending["entry_file_type"] = listing_entry_form.cleaned_data[
            "listing_entry_file_type"
        ]
        updated_pending["receipt_id"] = listing_entry_form.cleaned_data[
            "listing_entry_receipt_id"
        ].id
        updated_pending["stage"] = "upload"
        request.session["pallet_listing_pending"] = updated_pending
        request.session.pop("pallet_listing_last_incomplete_product_ids", None)
        pending = updated_pending
        response = redirect("scan:scan_receive_listing")

    listing_meta = hydrate_listing_state_from_pending(listing_state, pending)
    if request.method == "GET":
        _restore_listing_stage_from_pending(listing_state, pending)

    if response is None and request.method == "POST" and action != "listing_configure":
        response = handle_pallet_listing_action(
            request,
            action=action,
            state=listing_state,
        )
        pending = request.session.get("pallet_listing_pending")
        listing_meta = hydrate_listing_state_from_pending(listing_state, pending)

    return {
        "response": response,
        "listing_entry_form": listing_entry_form,
        "listing_state": listing_state,
        "listing_meta": listing_meta,
        "pending": pending,
    }


def build_receive_listing_context(state):
    listing_state = state["listing_state"]
    pending = state["pending"]
    listing_entry_receipt_id = listing_state["listing_entry_receipt_id"]
    visible_columns = build_listing_visible_columns(listing_state["listing_rows"])
    return {
        "active": "receive_listing",
        "listing_entry_form": state["listing_entry_form"],
        "listing_stage": listing_state["listing_stage"],
        "listing_columns": listing_state["listing_columns"],
        "listing_rows": listing_state["listing_rows"],
        "listing_group_suggestions": listing_state["listing_group_suggestions"],
        "listing_errors": listing_state["listing_errors"],
        "listing_token": pending.get("token") if pending else "",
        "listing_meta": state["listing_meta"],
        "mapping_fields": PALLET_LISTING_MAPPING_FIELDS,
        "review_fields": visible_columns["review_fields"] or PALLET_REVIEW_FIELDS,
        "location_fields": visible_columns["location_fields"],
        "show_rack_color_column": visible_columns["show_rack_color_column"],
        "listing_sheet_names": listing_state["listing_sheet_names"],
        "listing_sheet_name": listing_state["listing_sheet_name"],
        "listing_header_row": listing_state["listing_header_row"],
        "listing_pdf_pages_mode": listing_state["listing_pdf_pages_mode"],
        "listing_pdf_page_start": listing_state["listing_pdf_page_start"],
        "listing_pdf_page_end": listing_state["listing_pdf_page_end"],
        "listing_pdf_total_pages": listing_state["listing_pdf_total_pages"],
        "listing_pdf_analysis": listing_state["listing_pdf_analysis"],
        "listing_file_type": listing_state["listing_file_type"],
        "listing_entry_file_type": listing_state["listing_entry_file_type"],
        "listing_entry_receipt_id": listing_entry_receipt_id,
        "listing_selected_receipt": listing_state["listing_selected_receipt"],
        "listing_focus_card_id": _resolve_listing_focus_card_id(listing_state),
        "listing_suggestions_total_count": len(listing_state["listing_group_suggestions"]),
    }
