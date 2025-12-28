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
    cartons = shipment.carton_set.all().order_by("code")
    item_rows = build_shipment_item_rows(shipment)
    aggregate_rows = build_shipment_aggregate_rows(shipment)
    carton_rows = build_carton_rows(cartons)
    weight_total_g = compute_weight_total_g(carton_rows)
    weight_total_kg = weight_total_g / 1000 if weight_total_g else 0
    type_labels = build_shipment_type_labels(shipment)
    destination_city, destination_iata, destination_label = _build_destination_info(
        shipment
    )
    shipper_info = build_contact_info(TAG_SHIPPER, shipment.shipper_name)
    recipient_info = build_contact_info(TAG_RECIPIENT, shipment.recipient_name)
    correspondent_info = build_contact_info(TAG_CORRESPONDENT, shipment.correspondent_name)

    description = f"{cartons.count()} cartons, {len(aggregate_rows)} produits"
    if shipment.requested_delivery_date:
        description += (
            f", livraison souhaitee "
            f"{shipment.requested_delivery_date.strftime('%d/%m/%Y')}"
        )
    rows_for_template = (
        aggregate_rows if doc_type == "packing_list_shipment" else item_rows
    )

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
        "carton_count": cartons.count(),
        "carton_rows": carton_rows,
        "item_rows": rows_for_template,
        "aggregate_rows": aggregate_rows,
        "weight_total_g": weight_total_g,
        "weight_total_kg": weight_total_kg,
        "type_labels": type_labels,
        "shipper_info": shipper_info,
        "recipient_info": recipient_info,
        "correspondent_info": correspondent_info,
        "donor_name": shipment.shipper_name,
        "donation_description": shipment.notes or description,
        "humanitarian_purpose": shipment.notes or "Aide humanitaire",
        "shipment_description": description,
    }


def build_carton_document_context(shipment, carton):
    item_rows = []
    for item in carton.cartonitem_set.select_related(
        "product_lot", "product_lot__product"
    ):
        item_rows.append(
            {
                "product": item.product_lot.product.name,
                "lot": item.product_lot.lot_code or "N/A",
                "quantity": item.quantity,
            }
        )

    return {
        "document_date": timezone.localdate(),
        "shipment_ref": shipment.reference,
        "carton_code": carton.code,
        "item_rows": item_rows,
    }


def build_label_context(shipment, *, position, total):
    city, iata, _label = _build_destination_info(shipment)
    label_city = (city or shipment.destination_address or "").upper()
    label_iata = (iata or "").upper()
    return {
        "label_city": label_city,
        "label_iata": label_iata,
        "label_shipment_ref": shipment.reference,
        "label_position": position,
        "label_total": total,
        "shipment_ref": shipment.reference,
        "position": position,
        "total": total,
    }


def build_sample_document_context(doc_type):
    today = timezone.localdate()
    item_rows = [
        {"product": "Compresses", "lot": "LOT-01", "quantity": 12},
        {"product": "Seringues", "lot": "LOT-02", "quantity": 8},
    ]
    aggregate_rows = [
        {"product": "Compresses", "quantity": 20, "lots": "LOT-01, LOT-02"},
        {"product": "Seringues", "quantity": 8, "lots": "LOT-02"},
    ]
    carton_rows = [
        {"code": "C001", "weight_g": 1200, "volume_cm3": 800},
        {"code": "C002", "weight_g": 900, "volume_cm3": 600},
    ]
    weight_total_g = compute_weight_total_g(carton_rows)
    weight_total_kg = weight_total_g / 1000 if weight_total_g else 0
    rows_for_template = (
        aggregate_rows if doc_type == "packing_list_shipment" else item_rows
    )
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
        "item_rows": rows_for_template,
        "aggregate_rows": aggregate_rows,
        "weight_total_g": weight_total_g,
        "weight_total_kg": weight_total_kg,
        "type_labels": "Pharmacie",
        "shipper_info": shipper_info,
        "recipient_info": recipient_info,
        "correspondent_info": correspondent_info,
        "donor_name": "ASF",
        "donation_description": "Materiel medical",
        "humanitarian_purpose": "Aide humanitaire",
        "shipment_description": "Exemple de description",
    }


def build_sample_label_context():
    return {
        "label_city": "BAMAKO",
        "label_iata": "BKO",
        "label_shipment_ref": "BE 240316",
        "label_position": 1,
        "label_total": 10,
        "shipment_ref": "BE 240316",
        "position": 1,
        "total": 10,
    }


def build_preview_context(doc_type, shipment=None, carton=None):
    if doc_type == "shipment_label":
        if shipment:
            return build_label_context(shipment, position=1, total=10)
        return build_sample_label_context()

    if shipment:
        if doc_type == "packing_list_carton":
            carton = carton or shipment.carton_set.first()
            if carton:
                return build_carton_document_context(shipment, carton)
        return build_shipment_document_context(shipment, doc_type)

    return build_sample_document_context(doc_type)
