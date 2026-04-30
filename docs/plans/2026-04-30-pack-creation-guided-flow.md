# Pack Creation Guided Flow

## Goal

Simplify `/scan/pack/` without adding a second carton creation semantic.

The accepted direction is to keep line quantities as total quantities to prepare, then
choose automatic carton calculation or a manual carton count. A line-level `Qté / colis`
helper may fill the manual count, but the server continues to rely on
`forced_carton_count` for the actual split.

## Classification

- Primary: A. ASF operational need.
- Secondary: B. generic reusable capability.

This is a carton and stock-adjacent workflow, so the change must be reversible, keep
stock mutation paths unchanged, and preserve shipment readiness truth.

## UX Contract

- `Contenu`: scan/search product lines, total quantity, optional quantity per carton.
- `Répartition`: choose `Auto` or `Manuel`; manual posts `forced_carton_count`.
- `Affectation`: optionally preassign destination or shipment through existing fields.
- `Sortie`: preserve the missing-dimensions confirmation switch.
- `Validation`: keep the existing documentary and available preparation actions.

## Safety Contract

- No dedicated free-carton batch action is exposed.
- Stale `prepare_available_batch` posts are rejected with a non-field form error.
- `Qté / colis` is client-side only and never changes the server-side meaning of line
  quantities.
- Unassigned available cartons remain assignable later from `Vue Colis`.

## Reference Tests

- `wms.tests.orders.tests_pack_handlers.PackHandlersTests.test_handle_pack_post_auto_distribution_ignores_stale_forced_carton_count`
- `wms.tests.orders.tests_pack_handlers.PackHandlersTests.test_handle_pack_post_rejects_deprecated_free_batch_action`
- `wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_pack_uses_guided_creation_sections_and_hides_location_admin_action`
- `wms.tests.views.tests_views_scan_shipments.ScanShipmentsViewsTests.test_scan_pack_rejects_deprecated_free_batch_action_from_view`
- `wms.tests.views.tests_scan_bootstrap_ui.ScanBootstrapUiTests.test_scan_pack_line_layout_splits_search_and_select_and_places_scan_on_first_row`
