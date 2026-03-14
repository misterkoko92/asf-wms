# Shipment Planning Portal Selection Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align legacy Scan shipment creation, Portal order creation, domain order-to-shipment creation, and Planning shipment-party consumption so the same destination and actor combination is accepted or rejected everywhere.

**Architecture:** Add one shared legacy Django helper module for shipment-party normalization and shipment-party eligibility. Wire Scan, Portal, domain order creation, and Planning reference building to that shared layer instead of letting each surface prepare org-role inputs independently. Preserve legacy behavior when the org-role engine is disabled.

**Tech Stack:** Django forms/views/models, legacy WMS helpers, org-role resolvers, Django test runner

---

### Task 1: Create the shared shipment-party rule layer

**Files:**
- Create: `wms/shipment_party_rules.py`
- Test: `wms/tests/shipment/tests_shipment_party_rules.py`
- Reference: `wms/organization_role_resolvers.py`

**Step 1: Write the failing tests**

Add tests for the shared API before creating the module. Cover:
- `normalize_party_contact_to_org(contact)` returns the linked organization when `contact.contact_type == PERSON` and `contact.organization_id` is set.
- `eligible_shipper_contacts_for_destination(destination)` returns shipper contacts in scope for the destination.
- `eligible_recipient_contacts_for_shipper_destination(shipper_contact=..., destination=...)` returns person contacts and organization contacts whose normalized organization is bound to the shipper and destination.
- `eligible_correspondent_contacts_for_destination(destination)` returns the destination correspondent when present.
- `build_party_contact_reference(contact, fallback_name="")` produces a stable reference payload even when the contact is `None`.

```python
from django.test import TestCase

from contacts.models import Contact, ContactType
from wms.shipment_party_rules import (
    build_party_contact_reference,
    eligible_recipient_contacts_for_shipper_destination,
    normalize_party_contact_to_org,
)


class ShipmentPartyRulesTests(TestCase):
    def test_normalize_party_contact_to_org_uses_person_organization(self):
        org = Contact.objects.create(
            name="Recipient Org",
            contact_type=ContactType.ORGANIZATION,
            is_active=True,
        )
        person = Contact.objects.create(
            name="Recipient Person",
            contact_type=ContactType.PERSON,
            organization=org,
            is_active=True,
        )

        self.assertEqual(normalize_party_contact_to_org(person), org)
```

**Step 2: Run the new test file to verify it fails**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_rules -v 2`

Expected: failure with `ModuleNotFoundError: No module named 'wms.shipment_party_rules'` or missing helper names.

**Step 3: Write the minimal shared helper module**

Implement the module with a small public API and keep org-role resolution in `wms/organization_role_resolvers.py`:

```python
from contacts.models import Contact, ContactType

from .organization_role_resolvers import (
    eligible_recipients_for_shipper_destination,
    eligible_shippers_for_destination,
    is_org_roles_engine_enabled,
)


def normalize_party_contact_to_org(contact):
    if contact is None:
        return None
    if (
        contact.contact_type == ContactType.PERSON
        and getattr(contact, "organization_id", None)
    ):
        return contact.organization
    return contact


def eligible_recipient_contacts_for_shipper_destination(*, shipper_contact, destination):
    shipper_org = normalize_party_contact_to_org(shipper_contact)
    eligible_orgs = eligible_recipients_for_shipper_destination(
        shipper_org=shipper_org,
        destination=destination,
    )
    eligible_org_ids = list(eligible_orgs.values_list("id", flat=True))
    return Contact.objects.filter(
        is_active=True,
    ).filter(
        Q(pk__in=eligible_org_ids) | Q(organization_id__in=eligible_org_ids)
    ).distinct()
```

Also add:
- `eligible_shipper_contacts_for_destination(destination)`
- `eligible_correspondent_contacts_for_destination(destination)`
- `build_party_contact_reference(contact, fallback_name="")`

**Step 4: Run the shared-rule tests again**

Run: `./.venv/bin/python manage.py test wms.tests.shipment.tests_shipment_party_rules -v 2`

Expected: PASS.

**Step 5: Commit the shared helper layer**

```bash
git add wms/shipment_party_rules.py wms/tests/shipment/tests_shipment_party_rules.py
git commit -m "feat: add shared shipment party rules"
```

### Task 2: Align Scan shipment forms and handlers with the shared rules

**Files:**
- Modify: `wms/forms.py`
- Modify: `wms/scan_shipment_handlers.py`
- Modify: `wms/shipment_helpers.py`
- Test: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Test: `wms/tests/forms/tests_forms.py`
- Test: `wms/tests/views/tests_views_scan_shipments.py`
- Test: `wms/tests/scan/tests_scan_shipment_handlers.py`

**Step 1: Add or extend failing Scan tests**

Cover these cases:
- `ScanShipmentForm` uses `eligible_shipper_contacts_for_destination()` for the shipper queryset.
- `ScanShipmentForm` uses `eligible_recipient_contacts_for_shipper_destination()` for the recipient queryset, including person contacts attached to bound organizations.
- draft save and final validation normalize shipper and recipient contacts before calling the org-role resolvers.
- shipment selector payloads still expose the same grouped UI data after the backend switch.

```python
def test_scan_shipment_form_filters_person_recipients_via_shared_rules(self):
    form = ScanShipmentForm(
        destination_id=str(destination.id),
        initial={"shipper_contact": str(shipper_person.id)},
    )

    recipient_ids = set(form.fields["recipient_contact"].queryset.values_list("id", flat=True))
    self.assertIn(recipient_person.id, recipient_ids)
    self.assertNotIn(blocked_person.id, recipient_ids)
```

**Step 2: Run the focused Scan suites and confirm the new expectation fails**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.forms.tests_forms wms.tests.views.tests_views_scan_shipments wms.tests.scan.tests_scan_shipment_handlers -v 2`

Expected: the new assertion fails because `forms.py` still builds part of the actor logic locally.

**Step 3: Replace Scan-specific actor filtering with the shared helper**

Update `wms/forms.py` to:
- import the new helper functions from `wms/shipment_party_rules.py`
- build the shipper queryset from `eligible_shipper_contacts_for_destination()` when the engine is enabled
- build the recipient queryset from `eligible_recipient_contacts_for_shipper_destination()`
- keep current fallback behavior when the org-role engine is disabled

Update `wms/scan_shipment_handlers.py` and `wms/shipment_helpers.py` to normalize actor contacts before calling `resolve_shipper_for_operation()` and `resolve_recipient_binding_for_operation()`.

```python
from .shipment_party_rules import (
    eligible_recipient_contacts_for_shipper_destination,
    eligible_shipper_contacts_for_destination,
    normalize_party_contact_to_org,
)

shipper_org = normalize_party_contact_to_org(shipper_contact)
recipient_org = normalize_party_contact_to_org(recipient_contact)
resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)
resolve_recipient_binding_for_operation(
    shipper_org=shipper_org,
    recipient_org=recipient_org,
    destination=destination,
)
```

**Step 4: Re-run the focused Scan suites**

Run: `./.venv/bin/python manage.py test wms.tests.forms.tests_forms_org_roles_gate wms.tests.forms.tests_forms wms.tests.views.tests_views_scan_shipments wms.tests.scan.tests_scan_shipment_handlers -v 2`

Expected: PASS.

**Step 5: Commit the Scan integration**

```bash
git add wms/forms.py wms/scan_shipment_handlers.py wms/shipment_helpers.py \
  wms/tests/forms/tests_forms_org_roles_gate.py wms/tests/forms/tests_forms.py \
  wms/tests/views/tests_views_scan_shipments.py wms/tests/scan/tests_scan_shipment_handlers.py
git commit -m "feat: align scan shipment actor rules"
```

### Task 3: Align Portal order recipient filtering and validation

**Files:**
- Modify: `wms/views_portal_orders.py`
- Test: `wms/tests/views/tests_views_portal.py`

**Step 1: Add failing Portal tests for visible recipient filtering**

Add tests proving:
- a recipient whose synced contact is not bound to `profile.contact + destination` is excluded from the visible options
- a bound recipient remains selectable
- `self` remains available
- a POST with a now-hidden recipient id is rejected before order creation

```python
def test_portal_order_create_filters_recipient_options_by_shipper_and_destination(self):
    response = self.client.post(
        self.order_create_url,
        {"destination_id": str(self.destination.id), "recipient_id": "", "notes": ""},
    )

    recipient_ids = {option["id"] for option in response.context["recipient_options"]}
    self.assertIn("self", recipient_ids)
    self.assertIn(str(bound_recipient.id), recipient_ids)
    self.assertNotIn(str(blocked_recipient.id), recipient_ids)
```

**Step 2: Run the Portal order tests and confirm the new case fails**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: failure because `wms/views_portal_orders.py` still filters most recipient options only by destination.

**Step 3: Rebuild Portal recipient options through the shared rule layer**

Update `wms/views_portal_orders.py` to:
- normalize `profile.contact` through `normalize_party_contact_to_org()` before org-role validation
- compute allowed recipient contact ids with `eligible_recipient_contacts_for_shipper_destination()`
- keep only `AssociationRecipient` rows whose synced contact is allowed for the selected destination
- reuse the same filtered id set for GET re-render and POST validation

```python
allowed_contacts = eligible_recipient_contacts_for_shipper_destination(
    shipper_contact=profile.contact,
    destination=selected_destination,
)
allowed_contact_ids = set(allowed_contacts.values_list("id", flat=True))

recipient_options = [
    option
    for option in recipient_options_all
    if option["id"] == RECIPIENT_SELF
    or option.get("synced_contact_id") in allowed_contact_ids
]
```

**Step 4: Re-run the Portal view suite**

Run: `./.venv/bin/python manage.py test wms.tests.views.tests_views_portal -v 2`

Expected: PASS.

**Step 5: Commit the Portal integration**

```bash
git add wms/views_portal_orders.py wms/tests/views/tests_views_portal.py
git commit -m "feat: align portal recipient selection rules"
```

### Task 4: Align domain order-to-shipment creation with the shared rules

**Files:**
- Modify: `wms/domain/orders.py`
- Test: `wms/tests/domain/tests_domain_orders_org_roles.py`

**Step 1: Add failing domain tests for person-to-organization normalization**

Add tests proving:
- an order using `shipper_contact` and `recipient_contact` as person contacts linked to valid organizations still creates the shipment when the underlying org binding exists
- an order still fails when the normalized organizations are not bound

```python
def test_create_shipment_for_order_normalizes_person_contacts_to_org_roles(self):
    shipment = create_shipment_for_order(order=order)

    self.assertEqual(shipment.shipper_contact_ref_id, shipper_person.id)
    self.assertEqual(shipment.recipient_contact_ref_id, recipient_person.id)
    self.assertEqual(shipment.destination_id, destination.id)
```

**Step 2: Run the domain-order test file and confirm the new case fails**

Run: `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles -v 2`

Expected: failure because `wms/domain/orders.py` still calls the org-role resolvers with raw contact refs.

**Step 3: Normalize actor contacts before resolver calls**

Update `wms/domain/orders.py` to:
- keep the active contact refs stored on the order and shipment
- normalize shipper and recipient contacts to their business organization before calling the org-role resolvers
- leave the non-org-role path unchanged

```python
shipper_contact = _resolve_shipper_contact_for_order(order)
recipient_contact = _resolve_recipient_contact_for_order(order)
shipper_org = normalize_party_contact_to_org(shipper_contact)
recipient_org = normalize_party_contact_to_org(recipient_contact)

resolve_shipper_for_operation(shipper_org=shipper_org, destination=destination)
resolve_recipient_binding_for_operation(
    shipper_org=shipper_org,
    recipient_org=recipient_org,
    destination=destination,
)
```

**Step 4: Re-run the domain-order tests**

Run: `./.venv/bin/python manage.py test wms.tests.domain.tests_domain_orders_org_roles -v 2`

Expected: PASS.

**Step 5: Commit the domain-order integration**

```bash
git add wms/domain/orders.py wms/tests/domain/tests_domain_orders_org_roles.py
git commit -m "feat: align order shipment actor normalization"
```

### Task 5: Align Planning shipment-party references with the shared rules

**Files:**
- Create: `wms/tests/planning/tests_sources.py`
- Modify: `wms/planning/sources.py`
- Verify: `wms/planning/communication_plan.py`
- Verify: `wms/tests/planning/tests_communication_plan.py`

**Step 1: Add failing Planning source tests**

Create a dedicated suite for `wms/planning/sources.py` instead of hiding this logic inside broader communication tests. Cover:
- `build_shipper_reference(shipment)` uses the normalized organization contact when `shipment.shipper_contact_ref` is a person attached to an organization
- `build_recipient_reference(shipment)` does the same for recipients
- `build_correspondent_reference(shipment)` still falls back to `shipment.destination.correspondent_contact`
- the resulting payload keeps stable emails and names for communication consumers

```python
def test_build_shipper_reference_normalizes_person_contact_to_org(self):
    reference = build_shipper_reference(shipment)

    self.assertEqual(reference["contact_id"], shipper_org.id)
    self.assertEqual(reference["contact_name"], shipper_org.name)
```

**Step 2: Run the new Planning source tests and confirm they fail**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_sources -v 2`

Expected: failure because `wms/planning/sources.py` still builds references directly from `shipment.*_contact_ref`.

**Step 3: Build Planning references through the shared helper**

Update `wms/planning/sources.py` to:
- import `normalize_party_contact_to_org()` and `build_party_contact_reference()`
- normalize shipper and recipient references before building the payload
- keep association-profile email override for shippers, but look it up on the normalized organization contact
- keep `communication_plan.py` unchanged unless the new source tests prove a downstream mismatch

```python
contact = normalize_party_contact_to_org(shipment.shipper_contact_ref)
reference = build_party_contact_reference(contact, fallback_name=shipment.shipper_name)
```

If a downstream assertion breaks, add or adjust one focused communication-plan test in `wms/tests/planning/tests_communication_plan.py`.

**Step 4: Re-run the focused Planning suites**

Run: `./.venv/bin/python manage.py test wms.tests.planning.tests_sources wms.tests.planning.tests_communication_plan -v 2`

Expected: PASS.

**Step 5: Commit the Planning integration**

```bash
git add wms/planning/sources.py wms/tests/planning/tests_sources.py \
  wms/planning/communication_plan.py wms/tests/planning/tests_communication_plan.py
git commit -m "feat: align planning shipment party references"
```

### Task 6: Run the cross-surface regression suite

**Files:**
- Verify: `wms/tests/shipment/tests_shipment_party_rules.py`
- Verify: `wms/tests/forms/tests_forms_org_roles_gate.py`
- Verify: `wms/tests/forms/tests_forms.py`
- Verify: `wms/tests/views/tests_views_scan_shipments.py`
- Verify: `wms/tests/scan/tests_scan_shipment_handlers.py`
- Verify: `wms/tests/views/tests_views_portal.py`
- Verify: `wms/tests/domain/tests_domain_orders_org_roles.py`
- Verify: `wms/tests/planning/tests_sources.py`
- Verify: `wms/tests/planning/tests_communication_plan.py`

**Step 1: Run the shared-rule, Scan, Portal, domain-order, and Planning suites together**

Run:

```bash
./.venv/bin/python manage.py test \
  wms.tests.shipment.tests_shipment_party_rules \
  wms.tests.forms.tests_forms_org_roles_gate \
  wms.tests.forms.tests_forms \
  wms.tests.views.tests_views_scan_shipments \
  wms.tests.scan.tests_scan_shipment_handlers \
  wms.tests.views.tests_views_portal \
  wms.tests.domain.tests_domain_orders_org_roles \
  wms.tests.planning.tests_sources \
  wms.tests.planning.tests_communication_plan \
  -v 2
```

Expected: PASS.

**Step 2: If any failure remains, fix the smallest surface first**

Order of fixes:
1. `wms/shipment_party_rules.py`
2. `wms/forms.py` / `wms/scan_shipment_handlers.py`
3. `wms/views_portal_orders.py`
4. `wms/domain/orders.py`
5. `wms/planning/sources.py`

Do not broaden the fix into statuses, notifications, or Planning solver behavior.

**Step 3: Re-run the same regression command**

Run the same command from Step 1 until it passes cleanly.

Expected: PASS with no newly introduced failures in the harmonized surfaces.

**Step 4: Review the final diff for scope drift**

Run:

```bash
git diff --stat main...
git diff main... -- wms/shipment_party_rules.py wms/forms.py wms/scan_shipment_handlers.py \
  wms/shipment_helpers.py wms/views_portal_orders.py wms/domain/orders.py \
  wms/planning/sources.py wms/planning/communication_plan.py \
  wms/tests/shipment/tests_shipment_party_rules.py wms/tests/forms/tests_forms_org_roles_gate.py \
  wms/tests/forms/tests_forms.py wms/tests/views/tests_views_scan_shipments.py \
  wms/tests/scan/tests_scan_shipment_handlers.py wms/tests/views/tests_views_portal.py \
  wms/tests/domain/tests_domain_orders_org_roles.py wms/tests/planning/tests_sources.py \
  wms/tests/planning/tests_communication_plan.py
```

Expected: only shipment-party rule harmonization files are touched.

**Step 5: Commit the final regression pass**

```bash
git add -A
git commit -m "test: verify shipment party rule harmonization"
```
