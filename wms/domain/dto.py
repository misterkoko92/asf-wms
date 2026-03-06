from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ReceiveStockInput:
    product_id: int
    quantity: int
    location_id: int
    lot_code: str = ""
    received_on: date | None = None
    expires_on: date | None = None
    status: str | None = None
    storage_conditions: str | None = None
    source_receipt_id: int | None = None

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantité invalide.")


@dataclass(frozen=True)
class PackCartonInput:
    product_id: int
    quantity: int
    carton_id: int | None = None
    carton_code: str | None = None
    shipment_id: int | None = None
    current_location_id: int | None = None

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantité invalide.")
        if self.carton_id and self.carton_code:
            raise ValueError("Choisissez carton_id ou carton_code.")
