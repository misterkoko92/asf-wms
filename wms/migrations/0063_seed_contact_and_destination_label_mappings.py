from django.db import migrations


PACK_DOCUMENT_MAPPINGS = (
    {
        "pack_code": "C",
        "doc_type": "contact_label",
        "variant": "shipment",
        "mappings": (
            ("Feuil1", "A5", "shipment.shipper.title_name", "", False),
            ("Feuil1", "B5", "shipment.shipper.structure_name", "", False),
            ("Feuil1", "C5", "shipment.shipper.postal_address_full", "", False),
            ("Feuil1", "D5", "shipment.shipper.contact_primary", "", False),
            ("Feuil1", "A10", "shipment.recipient.title_name", "", False),
            ("Feuil1", "B10", "shipment.recipient.structure_name", "", False),
            ("Feuil1", "C10", "shipment.recipient.postal_address_full", "", False),
            ("Feuil1", "D10", "shipment.recipient.contact_primary", "", False),
            ("Feuil1", "A15", "shipment.correspondent.title_name", "", False),
            ("Feuil1", "B15", "shipment.correspondent.structure_name", "", False),
            ("Feuil1", "C15", "shipment.correspondent.postal_address_full", "", False),
            ("Feuil1", "D15", "shipment.correspondent.contact_primary", "", False),
        ),
    },
    {
        "pack_code": "D",
        "doc_type": "destination_label",
        "variant": "single_label",
        "mappings": (
            ("Feuil1", "A2", "shipment.destination_city", "upper", False),
            ("Feuil1", "C4", "shipment.destination_iata", "upper", False),
            ("Feuil1", "A7", "shipment.reference", "", False),
            ("Feuil1", "D7", "carton.position", "", False),
            ("Feuil1", "E7", "shipment.carton_total_count", "", False),
        ),
    },
    {
        "pack_code": "D",
        "doc_type": "destination_label",
        "variant": "all_labels",
        "mappings": (
            ("Feuil1", "A2", "shipment.destination_city", "upper", False),
            ("Feuil1", "C4", "shipment.destination_iata", "upper", False),
            ("Feuil1", "A7", "shipment.reference", "", False),
            ("Feuil1", "D7", "carton.position", "", False),
            ("Feuil1", "E7", "shipment.carton_total_count", "", False),
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


def seed_contact_and_destination_label_mappings(apps, schema_editor):
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
        ("wms", "0062_seed_default_print_pack_cell_mappings"),
    ]

    operations = [
        migrations.RunPython(
            seed_contact_and_destination_label_mappings,
            migrations.RunPython.noop,
        ),
    ]
