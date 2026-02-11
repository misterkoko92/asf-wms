from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ReceiveStockInput:
    product_id: int
    quantity: int
    location_id: int
    lot_code: str = ""
    received_on: Optional[date] = None
    expires_on: Optional[date] = None
    status: Optional[str] = None
    storage_conditions: Optional[str] = None
    source_receipt_id: Optional[int] = None

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantité invalide.")


@dataclass(frozen=True)
class PackCartonInput:
    product_id: int
    quantity: int
    carton_id: Optional[int] = None
    carton_code: Optional[str] = None
    shipment_id: Optional[int] = None
    current_location_id: Optional[int] = None

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantité invalide.")
        if self.carton_id and self.carton_code:
            raise ValueError("Choisissez carton_id ou carton_code.")
