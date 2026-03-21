from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BeContactDataset:
    contacts: list[dict] = field(default_factory=list)
    donors: list[dict] = field(default_factory=list)
    transporters: list[dict] = field(default_factory=list)
    volunteers: list[dict] = field(default_factory=list)
    shippers: list[dict] = field(default_factory=list)
    recipients: list[dict] = field(default_factory=list)
    correspondents: list[dict] = field(default_factory=list)
    destinations: list[dict] = field(default_factory=list)
    shipment_links: list[dict] = field(default_factory=list)
    review_items: list[dict] = field(default_factory=list)
    source_sheets: list[str] = field(default_factory=list)
