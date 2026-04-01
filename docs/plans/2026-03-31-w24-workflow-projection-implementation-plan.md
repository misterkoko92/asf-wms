# W2.4 Workflow Projection Implementation Plan

## Step 1

Add the read model.

- create `ShipmentWorkflowProjection`
- expose it via `wms.models`
- add migration

## Step 2

Create projection recomputation helpers.

- compute timeline markers
- compute lead times
- compute current segment
- compute delay state and active blockage category
- write single-shipment rebuild helper

## Step 3

Wire projection refresh into mutation paths.

- shipment create / edit
- tracking event creation
- dispute actions
- shipment close

## Step 4

Add rebuild command.

- `rebuild_workflow_projections`
- full rebuild for all shipments

## Step 5

Add reporting endpoint.

- `GET /api/v1/workflow-projections/shipments/`
- basic filters from the design
- stable payload tests

## Step 6

Update docs and shared reference.

- repo-reference key flow and shared contract
- operations note for rebuild command

## Step 7

Verification.

- targeted projection tests
- targeted API tests
- rebuild command test
- ruff on touched Python files
