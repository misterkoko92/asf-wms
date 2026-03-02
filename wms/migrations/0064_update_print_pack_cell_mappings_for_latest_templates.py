from django.db import migrations


PACK_DOCUMENT_MAPPINGS = (
    {
        "pack_code": "A",
        "doc_type": "picking",
        "variant": "single_carton",
        "mappings": (
            ("Feuil1", "A11", "carton.code", "", True),
            ("Feuil1", "B11", "carton.position", "", False),
            ("Feuil1", "C11", "shipment.carton_total_count", "", False),
            ("Feuil1", "D11", "shipment.reference", "", False),
            ("Feuil1", "A14", "carton.items[].product_name", "", False),
            ("Feuil1", "B14", "carton.items[].brand", "", False),
            ("Feuil1", "C14", "carton.items[].quantity", "", False),
            ("Feuil1", "D14", "carton.items[].expires_on", "date_fr", False),
            ("Feuil1", "E14", "carton.items[].location", "", False),
        ),
    },
    {
        "pack_code": "C",
        "doc_type": "contact_label",
        "variant": "shipment",
        "mappings": (
            ("Feuil1", "A5", "shipment.shipper.title", "", False),
            ("Feuil1", "A6", "shipment.shipper.first_name", "", False),
            ("Feuil1", "A7", "shipment.shipper.last_name", "", False),
            ("Feuil1", "B5", "shipment.shipper.structure_name", "", False),
            ("Feuil1", "C5", "shipment.shipper.postal_address", "", False),
            ("Feuil1", "C6", "shipment.shipper.postal_code_city", "", False),
            ("Feuil1", "C7", "shipment.shipper.country", "", False),
            ("Feuil1", "D5", "shipment.shipper.phone_1", "", False),
            ("Feuil1", "D6", "shipment.shipper.email_1", "", False),
            ("Feuil1", "A12", "shipment.recipient.title", "", False),
            ("Feuil1", "A13", "shipment.recipient.first_name", "", False),
            ("Feuil1", "A14", "shipment.recipient.last_name", "", False),
            ("Feuil1", "B12", "shipment.recipient.structure_name", "", False),
            ("Feuil1", "C12", "shipment.recipient.postal_address", "", False),
            ("Feuil1", "C13", "shipment.recipient.postal_code_city", "", False),
            ("Feuil1", "C14", "shipment.recipient.country", "", False),
            ("Feuil1", "D12", "shipment.recipient.phone_1", "", False),
            ("Feuil1", "D13", "shipment.recipient.email_1", "", False),
            ("Feuil1", "A19", "shipment.correspondent.title", "", False),
            ("Feuil1", "A20", "shipment.correspondent.first_name", "", False),
            ("Feuil1", "A21", "shipment.correspondent.last_name", "", False),
            ("Feuil1", "B19", "shipment.correspondent.structure_name", "", False),
            ("Feuil1", "C19", "shipment.correspondent.postal_address", "", False),
            ("Feuil1", "C20", "shipment.correspondent.postal_code_city", "", False),
            ("Feuil1", "C21", "shipment.correspondent.country", "", False),
            ("Feuil1", "D19", "shipment.correspondent.phone_1", "", False),
            ("Feuil1", "D20", "shipment.correspondent.email_1", "", False),
        ),
    },
    {
        "pack_code": "C",
        "doc_type": "shipment_note",
        "variant": "shipment",
        "mappings": (
            ("Feuil1", "A11", "shipment.origin_city", "upper", False),
            ("Feuil1", "B11", "shipment.origin_iata", "upper", False),
            ("Feuil1", "C11", "shipment.destination_city", "upper", False),
            ("Feuil1", "D11", "shipment.destination_iata", "upper", False),
            ("Feuil1", "A15", "shipment.reference", "", False),
            ("Feuil1", "B15", "shipment.total_weight_label", "", False),
            ("Feuil1", "C15", "shipment.carton_total_count", "", False),
            ("Feuil1", "D15", "shipment.hors_format_total_count", "", False),
            ("Feuil1", "A24", "shipment.shipper.title", "", False),
            ("Feuil1", "A25", "shipment.shipper.first_name", "", False),
            ("Feuil1", "A26", "shipment.shipper.last_name", "", False),
            ("Feuil1", "B24", "shipment.shipper.structure_name", "", False),
            ("Feuil1", "C24", "shipment.shipper.postal_address", "", False),
            ("Feuil1", "C25", "shipment.shipper.postal_code_city", "", False),
            ("Feuil1", "C26", "shipment.shipper.country", "", False),
            ("Feuil1", "D24", "shipment.shipper.phone_1", "", False),
            ("Feuil1", "D25", "shipment.shipper.email_1", "", False),
            ("Feuil1", "A31", "shipment.recipient.title", "", False),
            ("Feuil1", "A32", "shipment.recipient.first_name", "", False),
            ("Feuil1", "A33", "shipment.recipient.last_name", "", False),
            ("Feuil1", "B31", "shipment.recipient.structure_name", "", False),
            ("Feuil1", "C31", "shipment.recipient.postal_address", "", False),
            ("Feuil1", "C32", "shipment.recipient.postal_code_city", "", False),
            ("Feuil1", "C33", "shipment.recipient.country", "", False),
            ("Feuil1", "D31", "shipment.recipient.phone_1", "", False),
            ("Feuil1", "D32", "shipment.recipient.email_1", "", False),
            ("Feuil1", "A38", "shipment.correspondent.title", "", False),
            ("Feuil1", "A39", "shipment.correspondent.first_name", "", False),
            ("Feuil1", "A40", "shipment.correspondent.last_name", "", False),
            ("Feuil1", "B38", "shipment.correspondent.structure_name", "", False),
            ("Feuil1", "C38", "shipment.correspondent.postal_address", "", False),
            ("Feuil1", "C39", "shipment.correspondent.postal_code_city", "", False),
            ("Feuil1", "C40", "shipment.correspondent.country", "", False),
            ("Feuil1", "D38", "shipment.correspondent.phone_1", "", False),
            ("Feuil1", "D39", "shipment.correspondent.email_1", "", False),
        ),
    },
)


def _sync_document_mappings(print_cell_mapping_model, pack_document, mappings):
    keep_keys = set()
    for sequence, mapping in enumerate(mappings, start=1):
        worksheet_name, cell_ref, source_key, transform, required = mapping
        print_cell_mapping_model.objects.update_or_create(
            pack_document=pack_document,
            worksheet_name=worksheet_name,
            cell_ref=cell_ref,
            defaults={
                "source_key": source_key,
                "transform": transform,
                "required": required,
                "sequence": sequence,
            },
        )
        keep_keys.add((worksheet_name, cell_ref))

    for existing_mapping in print_cell_mapping_model.objects.filter(
        pack_document=pack_document
    ):
        key = (existing_mapping.worksheet_name, existing_mapping.cell_ref)
        if key not in keep_keys:
            existing_mapping.delete()


def update_print_pack_cell_mappings_for_latest_templates(apps, schema_editor):
    del schema_editor

    print_pack_document_model = apps.get_model("wms", "PrintPackDocument")
    print_cell_mapping_model = apps.get_model("wms", "PrintCellMapping")

    for config in PACK_DOCUMENT_MAPPINGS:
        pack_document = print_pack_document_model.objects.filter(
            pack__code=config["pack_code"],
            doc_type=config["doc_type"],
            variant=config["variant"],
        ).first()
        if pack_document is None:
            continue
        _sync_document_mappings(
            print_cell_mapping_model,
            pack_document,
            config["mappings"],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0063_seed_contact_and_destination_label_mappings"),
    ]

    operations = [
        migrations.RunPython(
            update_print_pack_cell_mappings_for_latest_templates,
            migrations.RunPython.noop,
        ),
    ]
