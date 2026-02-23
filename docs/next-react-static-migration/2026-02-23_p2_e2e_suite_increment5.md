# E2E Suite - P2 UI API Workflows

- Date: 2026-02-23
- Project: asf-wms
- Framework: django-testcase

## Scenario Matrix

| Scenario ID | Journey | Type | Preconditions | Steps Summary | Expected Outcome | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| S-001 | Shipment docs and labels | happy | staff user + produit + destination + contacts | MAJ stock -> creation expedition -> label colis -> tracking complet -> upload doc -> lecture labels -> cloture | expedition cloturee, doc additionnel present, labels disponibles | high |
| S-002 | Shipment docs and labels | negative | staff user sans fichier valide | upload doc avec extension invalide ou shipment/carton inexistant | erreur API uniforme (`code`, `field_errors`) et aucun effet de bord | medium |
| S-003 | Print templates lifecycle | happy | superuser authentifie | lister templates -> lire un template -> patch `save` -> patch `reset` | versionning incremente et layout persiste/reinitialise | high |
| S-004 | Print templates lifecycle | negative | staff non superuser | appeler `/api/v1/ui/templates/*` | refus 403 `superuser_required` | medium |
| S-005 | Portal order and recipients/account | happy | profile association + destination active + stock dispo | create recipient -> create order -> patch recipient -> patch account -> read dashboard | ordre cree avec shipment associe, compte et recipient mis a jour | high |
| S-006 | Portal order and recipients/account | negative | profile association incomplet | destination invalide / contact account sans type | erreurs metier (`destination_invalid`, `contact_rows_invalid`) | medium |

## Fixture Plan

| Scenario ID | Required Data | Setup | Cleanup |
| --- | --- | --- | --- |
| S-001 | warehouse, location, product, product lot, destination, contacts | `UiApiE2EWorkflowsTests.setUp` + transitions tracking | DB de test detruite automatiquement |
| S-002 | idem S-001 + fichier invalide | endpoint direct avec payload invalide | DB de test detruite automatiquement |
| S-003 | superuser + template `shipment_note` | endpoint `PATCH /ui/templates/<doc_type>/` | DB de test detruite automatiquement |
| S-004 | staff non superuser | endpoint templates avec client staff | DB de test detruite automatiquement |
| S-005 | association profile + recipient + destination + product | endpoints portal mutations chaines | DB de test detruite automatiquement |
| S-006 | payload volontairement invalide | endpoints portal avec donnees invalides | DB de test detruite automatiquement |

## Integration Bridge

| Scenario ID | Required Integration Test | Status |
| --- | --- | --- |
| S-001 | `api.tests.tests_ui_e2e_workflows.UiApiE2EWorkflowsTests::test_e2e_scan_workflow_stock_to_close_with_docs_labels_templates` | covered |
| S-002 | `api.tests.tests_ui_endpoints::test_ui_shipment_documents_upload_delete_and_permissions` + `test_ui_shipment_labels_endpoints_return_urls` | covered |
| S-003 | `api.tests.tests_ui_endpoints::test_ui_template_detail_patch_and_reset` | covered |
| S-004 | `api.tests.tests_ui_endpoints::test_ui_templates_require_superuser` | covered |
| S-005 | `api.tests.tests_ui_e2e_workflows.UiApiE2EWorkflowsTests::test_e2e_portal_workflow_recipients_account_and_order` | covered |
| S-006 | `api.tests.tests_ui_endpoints::test_ui_portal_order_create_rejects_invalid_destination` + `test_ui_portal_account_patch_rejects_contact_without_type` | covered |

## Execution Notes

- Cadence recommandee: execution a chaque PR P2 et nightly sur `main`.
- Flake risk faible: tests DB Django deterministes (pas de clock externe ni API tierce).
- Test debt restant: E2E navigateur reel (Playwright) pour verifier interactions UI (upload DOM, edition JSON, navigation).
