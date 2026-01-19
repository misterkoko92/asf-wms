from django.utils import timezone

from .contact_filters import TAG_CORRESPONDENT, TAG_RECIPIENT, TAG_SHIPPER
from .documents import (
    build_carton_rows,
    build_contact_info,
    build_org_context,
    build_shipment_aggregate_rows,
    build_shipment_item_rows,
    build_shipment_type_labels,
    compute_weight_total_g,
)
from .scan_helpers import get_product_volume_cm3, get_product_weight_g
from .models import CartonFormat, CartonItem, RackColor


def _build_destination_info(shipment):
    if shipment.destination and shipment.destination.city:
        destination_city = shipment.destination.city
        destination_iata = shipment.destination.iata_code or ""
        destination_label = destination_city
        if destination_iata:
            destination_label = f"{destination_label} ({destination_iata})"
    else:
        destination_city = ""
        destination_iata = ""
        destination_label = shipment.destination_address
    return destination_city, destination_iata, destination_label


def build_shipment_document_context(shipment, doc_type):
    cartons = list(shipment.carton_set.all().order_by("code"))
    carton_labels = {
        carton.id: f"Colis N°{index}"
        for index, carton in enumerate(cartons, start=1)
    }
    item_rows = build_shipment_item_rows(shipment, carton_labels=carton_labels)
    aggregate_rows = build_shipment_aggregate_rows(shipment)
    default_format = CartonFormat.objects.filter(is_default=True).first()
    if default_format is None:
        default_format = CartonFormat.objects.first()
    carton_rows = build_carton_rows(cartons, default_format=default_format)
    missing_by_carton = {}
    for item in CartonItem.objects.filter(carton__shipment=shipment).select_related(
        "product_lot__product"
    ):
        product = item.product_lot.product
        if (
            get_product_weight_g(product) is None
            and get_product_volume_cm3(product) is None
        ):
            missing_by_carton[item.carton_id] = True

    has_missing_defaults = bool(missing_by_carton)
    hide_measurements = (
        doc_type in {"packing_list_shipment"} and has_missing_defaults
    )
    for index, row in enumerate(carton_rows, start=1):
        row["label"] = f"Colis N°{index}"
        if hide_measurements:
            row["weight_kg"] = None
            row["volume_m3"] = None
        else:
            row["weight_kg"] = row["weight_g"] / 1000 if row.get("weight_g") else None
            row["volume_m3"] = (
                row["volume_cm3"] / 1_000_000 if row.get("volume_cm3") else None
            )
        if row.get("length_cm") and row.get("width_cm") and row.get("height_cm"):
            row["dimensions_cm"] = (
                f"{row['length_cm']} x {row['width_cm']} x {row['height_cm']}"
            )
        else:
            row["dimensions_cm"] = None
    weight_total_g = compute_weight_total_g(carton_rows)
    weight_total_kg = weight_total_g / 1000 if weight_total_g else 0
    volume_total_m3 = sum(
        row["volume_cm3"] for row in carton_rows if row.get("volume_cm3")
    )
    volume_total_m3 = volume_total_m3 / 1_000_000 if volume_total_m3 else None
    if hide_measurements:
        weight_total_kg = None
        volume_total_m3 = None
    type_labels = build_shipment_type_labels(shipment)
    destination_city, destination_iata, destination_label = _build_destination_info(
        shipment
    )
    shipper_info = build_contact_info(TAG_SHIPPER, shipment.shipper_name)
    recipient_info = build_contact_info(TAG_RECIPIENT, shipment.recipient_name)
    correspondent_info = build_contact_info(TAG_CORRESPONDENT, shipment.correspondent_name)

    description = f"{len(cartons)} cartons, {len(aggregate_rows)} produits"
    if shipment.requested_delivery_date:
        description += (
            f", livraison souhaitee "
            f"{shipment.requested_delivery_date.strftime('%d/%m/%Y')}"
        )
    rows_for_template = item_rows

    return {
        **build_org_context(),
        "document_ref": f"DOC-{shipment.reference}-{doc_type}".upper(),
        "document_date": timezone.localdate(),
        "shipment_ref": shipment.reference,
        "shipper_name": shipment.shipper_name,
        "shipper_contact": shipment.shipper_contact,
        "recipient_name": shipment.recipient_name,
        "recipient_contact": shipment.recipient_contact,
        "correspondent_name": shipment.correspondent_name,
        "destination_address": shipment.destination_address,
        "destination_country": shipment.destination_country,
        "destination_label": destination_label,
        "destination_city": destination_city,
        "destination_iata": destination_iata,
        "carton_count": len(cartons),
        "carton_rows": carton_rows,
        "item_rows": rows_for_template,
        "aggregate_rows": aggregate_rows,
        "weight_total_g": weight_total_g,
        "weight_total_kg": weight_total_kg,
        "volume_total_m3": volume_total_m3,
        "type_labels": type_labels,
        "shipper_info": shipper_info,
        "recipient_info": recipient_info,
        "correspondent_info": correspondent_info,
        "donor_name": shipment.shipper_name,
        "donation_description": shipment.notes or description,
        "humanitarian_purpose": shipment.notes or "Aide humanitaire",
        "shipment_description": description,
        "hide_footer": doc_type == "packing_list_shipment",
        "show_carton_column": doc_type == "packing_list_shipment",
    }


def build_carton_document_context(shipment, carton):
    item_rows = []
    weight_total_g = 0
    has_missing_defaults = False
    for item in carton.cartonitem_set.select_related(
        "product_lot", "product_lot__product"
    ):
        product = item.product_lot.product
        if (
            get_product_weight_g(product) is None
            and get_product_volume_cm3(product) is None
        ):
            has_missing_defaults = True
        if product.weight_g:
            weight_total_g += product.weight_g * item.quantity
        item_rows.append(
            {
                "product": item.product_lot.product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
                "expires_on": item.product_lot.expires_on,
            }
        )

    return {
        "document_date": timezone.localdate(),
        "shipment_ref": shipment.reference,
        "carton_code": carton.code,
        "item_rows": item_rows,
        "carton_weight_kg": None
        if has_missing_defaults
        else (weight_total_g / 1000 if weight_total_g else None),
        "hide_footer": True,
    }


def build_carton_picking_context(carton):
    rows_by_key = {}
    for item in carton.cartonitem_set.select_related(
        "product_lot__product",
        "product_lot__location",
    ):
        product = item.product_lot.product
        location = item.product_lot.location
        if location:
            location_label = f"{location.zone} - {location.aisle} - {location.shelf}"
        else:
            location_label = "-"
        key = (product.id, location.id if location else None)
        if key not in rows_by_key:
            rows_by_key[key] = {
                "product": product.name,
                "quantity": item.quantity,
                "location": location_label,
            }
        else:
            rows_by_key[key]["quantity"] += item.quantity
    item_rows = sorted(
        rows_by_key.values(),
        key=lambda row: (row["product"], row["location"]),
    )
    return {
        "document_date": timezone.localdate(),
        "carton_code": carton.code,
        "item_rows": item_rows,
        "hide_footer": True,
    }


def build_label_context(shipment, *, position, total):
    city, iata, _label = _build_destination_info(shipment)
    label_city = (city or shipment.destination_address or "").upper()
    label_iata = (iata or "").upper()
    label_qr_url = shipment.qr_code_image.url if shipment.qr_code_image else ""
    return {
        "label_city": label_city,
        "label_iata": label_iata,
        "label_shipment_ref": shipment.reference,
        "label_position": position,
        "label_total": total,
        "label_qr_url": label_qr_url,
        "shipment_ref": shipment.reference,
        "position": position,
        "total": total,
    }


def build_sample_document_context(doc_type):
    today = timezone.localdate()
    aggregate_rows = [
        {"product": "Compresses", "quantity": 20, "lots": "LOT-01, LOT-02"},
        {"product": "Seringues", "quantity": 8, "lots": "LOT-02"},
    ]
    raw_carton_rows = [
        {"code": "C001", "weight_g": 1200, "volume_cm3": 800},
        {"code": "C002", "weight_g": 900, "volume_cm3": 600},
    ]
    weight_total_g = compute_weight_total_g(raw_carton_rows)
    weight_total_kg = weight_total_g / 1000 if weight_total_g else 0
    shipper_info = {
        "company": "ASF",
        "person": "Jean Dupont",
        "address": "10 rue Exemple\n75000 Paris",
        "phone": "+33 1 00 00 00 00",
        "email": "contact@example.org",
    }
    recipient_info = {
        "company": "Hopital Test",
        "person": "Marie Curie",
        "address": "1 avenue Demo\nABIDJAN",
        "phone": "+225 00 00 00 00",
        "email": "destinataire@example.org",
    }
    correspondent_info = {
        "company": "Correspondant Local",
        "person": "Amadou Diallo",
        "address": "Zone Aeroport\nABIDJAN",
        "phone": "+225 11 11 11 11",
        "email": "correspondant@example.org",
    }

    carton_rows = []
    for index, row in enumerate(raw_carton_rows, start=1):
        carton_rows.append(
            {
                "label": f"Colis N°{index}",
                "weight_kg": row["weight_g"] / 1000 if row["weight_g"] else None,
                "dimensions_cm": "40 x 30 x 30",
                "volume_m3": row["volume_cm3"] / 1_000_000 if row["volume_cm3"] else None,
            }
        )
    item_rows = [
        {
            "product": "Compresses",
            "lot": "LOT-01",
            "quantity": 12,
            "expires_on": today,
            "carton_label": "Colis N°1",
        },
        {
            "product": "Seringues",
            "lot": "LOT-02",
            "quantity": 8,
            "expires_on": today,
            "carton_label": "Colis N°2",
        },
    ]
    return {
        **build_org_context(),
        "document_ref": "DOC-TEST",
        "document_date": today,
        "shipment_ref": "YY0001",
        "shipper_name": "ASF",
        "shipper_contact": "Jean Dupont",
        "recipient_name": "Hopital Test",
        "recipient_contact": "Marie Curie",
        "correspondent_name": "Correspondant Local",
        "destination_address": "ABIDJAN - COTE D'IVOIRE",
        "destination_country": "COTE D'IVOIRE",
        "destination_label": "ABIDJAN (ABJ)",
        "destination_city": "ABIDJAN",
        "destination_iata": "ABJ",
        "carton_count": len(carton_rows),
        "carton_rows": carton_rows,
        "item_rows": item_rows,
        "aggregate_rows": aggregate_rows,
        "weight_total_g": weight_total_g,
        "weight_total_kg": weight_total_kg,
        "volume_total_m3": sum(
            row["volume_cm3"] for row in raw_carton_rows if row.get("volume_cm3")
        )
        / 1_000_000,
        "type_labels": "Pharmacie",
        "shipper_info": shipper_info,
        "recipient_info": recipient_info,
        "correspondent_info": correspondent_info,
        "donor_name": "ASF",
        "donation_description": "Materiel medical",
        "humanitarian_purpose": "Aide humanitaire",
        "shipment_description": "Exemple de description",
        "hide_footer": doc_type in {"packing_list_shipment", "packing_list_carton"},
        "show_carton_column": doc_type == "packing_list_shipment",
    }


def build_sample_label_context():
    return {
        "label_city": "BAMAKO",
        "label_iata": "BKO",
        "label_shipment_ref": "BE 240316",
        "label_position": 1,
        "label_total": 10,
        "label_qr_url": "",
        "shipment_ref": "BE 240316",
        "position": 1,
        "total": 10,
    }


def resolve_rack_color(location):
    if location is None:
        return None
    match = RackColor.objects.filter(
        warehouse=location.warehouse, zone__iexact=location.zone
    ).first()
    if match:
        return match.color
    return None


def build_product_label_context(product, rack_color=None):
    location = product.default_location
    rack = location.zone if location else ""
    aisle = location.aisle if location else ""
    shelf = location.shelf if location else ""
    if rack_color is None:
        rack_color = resolve_rack_color(location)
    return {
        "product_name": product.name,
        "product_brand": product.brand,
        "product_color": product.color,
        "product_photo_url": product.photo.url if product.photo else "",
        "product_rack": rack,
        "product_aisle": aisle,
        "product_shelf": shelf,
        "rack_color": rack_color,
    }


def build_sample_product_label_context():
    return {
        "product_name": "Seringue Luer Tip 1/3/5ml",
        "product_brand": "Divers",
        "product_color": "Blanc / Transparent",
        "product_photo_url": "",
        "product_rack": "4",
        "product_aisle": "IV - A1",
        "product_shelf": "A",
        "rack_color": "#1C8BC0",
    }


def build_product_qr_label_context(product):
    return {
        "product_name": product.name,
        "product_brand": product.brand,
        "product_qr_url": product.qr_code_image.url if product.qr_code_image else "",
    }


def build_sample_product_qr_label_context():
    return {
        "product_name": "Seringue Luer Tip 1/3/5ml",
        "product_brand": "Divers",
        "product_qr_url": "",
    }


def build_preview_context(doc_type, shipment=None, carton=None, product=None):
    if doc_type == "shipment_label":
        if shipment:
            return build_label_context(shipment, position=1, total=10)
        return build_sample_label_context()

    if doc_type == "product_label":
        if product:
            return build_product_label_context(product)
        return build_sample_product_label_context()
    if doc_type == "product_qr":
        if product:
            return build_product_qr_label_context(product)
        return build_sample_product_qr_label_context()

    if shipment:
        if doc_type == "packing_list_carton":
            carton = carton or shipment.carton_set.first()
            if carton:
                return build_carton_document_context(shipment, carton)
        return build_shipment_document_context(shipment, doc_type)

    return build_sample_document_context(doc_type)
