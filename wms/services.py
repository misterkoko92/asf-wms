"""Compatibility layer for legacy imports."""

from .domain.orders import (
    assign_ready_cartons_to_order,
    consume_reserved_stock,
    create_shipment_for_order,
    pack_carton_from_reserved,
    prepare_order,
    release_reserved_stock,
    reserve_stock_for_order,
)
from .domain.stock import (
    StockConsumeResult,
    StockError,
    adjust_stock,
    consume_stock,
    fefo_lots,
    generate_carton_code,
    pack_carton,
    pack_carton_from_input,
    receive_receipt_line,
    receive_stock,
    receive_stock_from_input,
    transfer_stock,
    unpack_carton,
)

__all__ = [
    "StockConsumeResult",
    "StockError",
    "adjust_stock",
    "assign_ready_cartons_to_order",
    "consume_reserved_stock",
    "consume_stock",
    "create_shipment_for_order",
    "fefo_lots",
    "generate_carton_code",
    "pack_carton",
    "pack_carton_from_input",
    "pack_carton_from_reserved",
    "prepare_order",
    "receive_receipt_line",
    "receive_stock",
    "receive_stock_from_input",
    "release_reserved_stock",
    "reserve_stock_for_order",
    "transfer_stock",
    "unpack_carton",
]
