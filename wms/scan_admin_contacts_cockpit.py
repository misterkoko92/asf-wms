from __future__ import annotations


def parse_cockpit_filters(*, role: str = "", shipper_org_id: str = "") -> dict:
    normalized_role = (role or "").strip().lower()
    normalized_shipper_org_id = (shipper_org_id or "").strip()
    return {
        "role": normalized_role,
        "shipper_org_id": normalized_shipper_org_id,
    }


def build_cockpit_context(*, query: str, filters: dict) -> dict:
    return {
        "query": query,
        "cockpit_filters": filters,
        "cockpit_rows": [],
        "cockpit_mode": "org_roles",
    }
