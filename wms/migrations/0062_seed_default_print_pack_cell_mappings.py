from django.db import migrations


PACK_DOCUMENT_MAPPINGS = (
    {
        "pack_code": "A",
        "doc_type": "picking",
        "variant": "single_carton",
        "mappings": (
            ("Feuil1", "A11", "carton.id", "", True),
            ("Feuil1", "B11", "carton.code", "", True),
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
        "pack_code": "B",
        "doc_type": "packing_list_shipment",
        "variant": "shipment",
        "mappings": (
            ("Feuil1", "A12", "shipment.reference", "", False),
            ("Feuil1", "B12", "shipment.carton_total_count", "", False),
            ("Feuil1", "C12", "shipment.destination_iata", "upper", False),
            ("Feuil1", "D12", "shipment.recipient_name", "", False),
            ("Feuil1", "A16", "shipment.items[].carton_position", "", False),
            ("Feuil1", "B16", "shipment.items[].category_root", "", False),
            ("Feuil1", "C16", "shipment.items[].product_name", "", False),
            ("Feuil1", "D16", "shipment.items[].quantity", "", False),
            ("Feuil1", "E16", "shipment.items[].expires_on", "date_fr", False),
        ),
    },
    {
        "pack_code": "B",
        "doc_type": "donation_certificate",
        "variant": "shipment",
        "mappings": (
            ("attestation donation", "B7", "shipment.destination_city", "upper", False),
            ("attestation donation", "C17", "shipment.recipient.title_name", "", False),
            ("attestation donation", "C18", "shipment.recipient.structure_name", "", False),
            ("attestation donation", "C19", "shipment.recipient.postal_address", "", False),
            ("attestation donation", "C20", "shipment.recipient.postal_code", "", False),
            ("attestation donation", "C21", "shipment.recipient.city", "", False),
            ("attestation donation", "E21", "shipment.recipient.country", "upper", False),
            ("attestation donation", "C23", "shipment.recipient.phone_1", "", False),
            ("attestation donation", "D23", "shipment.recipient.phone_2", "", False),
            ("attestation donation", "E23", "shipment.recipient.phone_3", "", False),
            ("attestation donation", "C24", "shipment.recipient.email_1", "", False),
            ("attestation donation", "D24", "shipment.recipient.email_2", "", False),
            ("attestation donation", "E24", "shipment.recipient.email_3", "", False),
            ("attestation donation", "C25", "shipment.recipient.emergency_contact", "", False),
            ("attestation donation", "D32", "document.generated_on", "date_fr", True),
        ),
    },
    {
        "pack_code": "B",
        "doc_type": "packing_list_carton",
        "variant": "per_carton_single",
        "mappings": (
            ("Feuil1", "B10", "carton.code", "", True),
            ("Feuil1", "A12", "carton.items[].category_root", "", False),
            ("Feuil1", "B12", "carton.items[].product_name", "", False),
            ("Feuil1", "C12", "carton.items[].quantity", "", False),
            ("Feuil1", "D12", "carton.items[].expires_on", "date_fr", False),
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
            ("Feuil1", "A24", "shipment.shipper.title_name", "", False),
            ("Feuil1", "B24", "shipment.shipper.structure_name", "", False),
            ("Feuil1", "C24", "shipment.shipper.postal_address_full", "", False),
            ("Feuil1", "D24", "shipment.shipper.contact_primary", "", False),
            ("Feuil1", "A29", "shipment.recipient.title_name", "", False),
            ("Feuil1", "B29", "shipment.recipient.structure_name", "", False),
            ("Feuil1", "C29", "shipment.recipient.postal_address_full", "", False),
            ("Feuil1", "D29", "shipment.recipient.contact_primary", "", False),
            ("Feuil1", "A34", "shipment.correspondent.title_name", "", False),
            ("Feuil1", "B34", "shipment.correspondent.structure_name", "", False),
            ("Feuil1", "C34", "shipment.correspondent.postal_address_full", "", False),
            ("Feuil1", "D34", "shipment.correspondent.contact_primary", "", False),
        ),
    },
)


def _sync_document_mappings(print_cell_mapping_model, pack_document, mappings):
    keep_keys = set()
    for sequence, mapping in enumerate(mappings, start=1):
        (
            worksheet_name,
            cell_ref,
            source_key,
            transform,
            required,
        ) = mapping
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


def seed_default_print_pack_cell_mappings(apps, schema_editor):
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
        ("wms", "0061_seed_default_print_pack_configuration"),
    ]

    operations = [
        migrations.RunPython(
            seed_default_print_pack_cell_mappings,
            migrations.RunPython.noop,
        ),
    ]
