# W2.3 Workflow Blockage Queue Implementation Plan

## Step 1

Add the lightweight claim persistence layer.

- create `WorkflowBlockageClaim`
- export it through `wms.models`
- add migration

## Step 2

Extract shared blockage-row computation.

- add a helper module dedicated to workflow blockage rows
- derive rows for `creation_expedition`, `commande`, `suivi`, `cloture`, `queue`
- merge derived rows with active claims
- expose summary counts for `open`, `claimed`, `unclaimed`

## Step 3

Wire the legacy dashboard.

- allow `scan_dashboard` POST
- add claim/release handler
- add `workflow_blockage_rows`
- promote top unclaimed blockage rows into `action_queue_rows`
- render the dedicated table in `templates/scan/dashboard.html`

## Step 4

Wire the UI API.

- mirror blockage rows in `UiDashboardView`
- add `UiDashboardWorkflowBlockageClaimView`
- register route in `api/v1/urls.py`

## Step 5

Cover the contract with tests.

- dashboard GET/POST tests
- API GET/POST tests
- queue derivation cases for email/document scan

## Step 6

Update operational docs.

- repo-reference key flows
- shared contract
- ops/release checklist wording for the new queue
