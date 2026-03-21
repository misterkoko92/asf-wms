from .models import ShipmentValidationStatus


def is_shipment_shipper_allowed(shipper) -> bool:
    if shipper is None:
        return True
    return bool(shipper.is_active) and (
        shipper.validation_status == ShipmentValidationStatus.VALIDATED
    )
