from .models import Carton, CartonFormat, CartonStatus
from .scan_parse import parse_decimal, parse_int

def build_available_cartons():
    cartons = (
        Carton.objects.filter(status=CartonStatus.PACKED, shipment__isnull=True)
        .prefetch_related("cartonitem_set__product_lot__product")
        .order_by("code")
    )
    options = []
    for carton in cartons:
        weight_total = 0
        for item in carton.cartonitem_set.all():
            product_weight = item.product_lot.product.weight_g or 0
            weight_total += product_weight * item.quantity
        options.append(
            {
                "id": carton.id,
                "code": carton.code,
                "weight_g": weight_total,
            }
        )
    return options


def build_carton_formats():
    formats = list(CartonFormat.objects.all().order_by("name"))
    default_format = next((fmt for fmt in formats if fmt.is_default), None)
    if default_format is None and formats:
        default_format = formats[0]
    data = []
    for fmt in formats:
        data.append(
            {
                "id": fmt.id,
                "name": fmt.name,
                "length_cm": fmt.length_cm,
                "width_cm": fmt.width_cm,
                "height_cm": fmt.height_cm,
                "max_weight_g": fmt.max_weight_g,
                "is_default": fmt.is_default,
            }
        )
    return data, default_format


def get_carton_volume_cm3(carton_size):
    return (
        carton_size["length_cm"]
        * carton_size["width_cm"]
        * carton_size["height_cm"]
    )


def resolve_carton_size(
    *, carton_format_id: str | None, default_format: CartonFormat | None, data
):
    errors = []
    if not carton_format_id and default_format:
        carton_format_id = str(default_format.id)

    if carton_format_id and carton_format_id != "custom":
        try:
            format_id = int(carton_format_id)
        except ValueError:
            format_id = None
        format_obj = (
            CartonFormat.objects.filter(id=format_id).first() if format_id else None
        )
        if not format_obj:
            errors.append("Format de carton invalide.")
            return None, errors
        return (
            {
                "length_cm": format_obj.length_cm,
                "width_cm": format_obj.width_cm,
                "height_cm": format_obj.height_cm,
                "max_weight_g": format_obj.max_weight_g,
            },
            errors,
        )

    length_cm = parse_decimal(data.get("carton_length_cm"))
    width_cm = parse_decimal(data.get("carton_width_cm"))
    height_cm = parse_decimal(data.get("carton_height_cm"))
    max_weight_g = parse_int(data.get("carton_max_weight_g"))
    if length_cm is None or length_cm <= 0:
        errors.append("Longueur carton invalide.")
    if width_cm is None or width_cm <= 0:
        errors.append("Largeur carton invalide.")
    if height_cm is None or height_cm <= 0:
        errors.append("Hauteur carton invalide.")
    if max_weight_g is None or max_weight_g <= 0:
        errors.append("Poids max carton invalide.")
    if errors:
        return None, errors
    return (
        {
            "length_cm": length_cm,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "max_weight_g": max_weight_g,
        },
        errors,
    )
