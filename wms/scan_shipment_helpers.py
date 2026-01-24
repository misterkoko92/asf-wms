from .models import Shipment

def build_shipment_line_values(carton_count, data=None):
    lines = []
    for index in range(1, carton_count + 1):
        prefix = f"line_{index}_"
        lines.append(
            {
                "carton_id": (data.get(prefix + "carton_id") if data else "") or "",
                "product_code": (data.get(prefix + "product_code") if data else "") or "",
                "quantity": (data.get(prefix + "quantity") if data else "") or "",
            }
        )
    return lines


def resolve_shipment(reference: str):
    reference = (reference or "").strip()
    if not reference:
        return None
    return Shipment.objects.filter(reference__iexact=reference).first()
