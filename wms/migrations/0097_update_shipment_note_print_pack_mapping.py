from django.db import migrations


SHIPMENT_NOTE_MAPPINGS = (
    ("Feuil1", "B7", "shipment.origin_city", "upper", False),
    ("Feuil1", "D7", "shipment.destination_city", "upper", False),
    ("Feuil1", "B8", "shipment.origin_iata", "upper", False),
    ("Feuil1", "D8", "shipment.destination_iata", "upper", False),
    ("Feuil1", "B10", "shipment.reference", "upper", False),
    ("Feuil1", "B11", "shipment.total_weight_label", "upper", False),
    ("Feuil1", "B12", "shipment.carton_total_count", "upper", False),
    ("Feuil1", "B18", "shipment.shipper.display_name", "upper", False),
    ("Feuil1", "B19", "shipment.shipper.structure_name", "upper", False),
    ("Feuil1", "B20", "shipment.shipper.postal_address_display", "upper", False),
    ("Feuil1", "B21", "shipment.shipper.email_1", "upper", False),
    ("Feuil1", "B22", "shipment.shipper.phone_1", "upper", False),
    ("Feuil1", "B25", "shipment.recipient.display_name", "upper", False),
    ("Feuil1", "B26", "shipment.recipient.structure_name", "upper", False),
    ("Feuil1", "B27", "shipment.recipient.postal_address_display", "upper", False),
    ("Feuil1", "B28", "shipment.recipient.email_1", "upper", False),
    ("Feuil1", "B29", "shipment.recipient.phone_1", "upper", False),
    ("Feuil1", "B32", "shipment.correspondent.display_name", "upper", False),
    ("Feuil1", "B33", "shipment.correspondent.structure_name", "upper", False),
    ("Feuil1", "B34", "shipment.correspondent.postal_address_display", "upper", False),
    ("Feuil1", "B35", "shipment.correspondent.email_1", "upper", False),
    ("Feuil1", "B36", "shipment.correspondent.phone_1", "upper", False),
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


def update_shipment_note_print_pack_mapping(apps, schema_editor):
    del schema_editor

    print_pack_document_model = apps.get_model("wms", "PrintPackDocument")
    print_cell_mapping_model = apps.get_model("wms", "PrintCellMapping")

    pack_document = print_pack_document_model.objects.filter(
        pack__code="C",
        doc_type="shipment_note",
        variant="shipment",
    ).first()
    if pack_document is None:
        return

    _sync_document_mappings(
        print_cell_mapping_model,
        pack_document,
        SHIPMENT_NOTE_MAPPINGS,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0096_remove_org_roles_runtime"),
    ]

    operations = [
        migrations.RunPython(
            update_shipment_note_print_pack_mapping,
            migrations.RunPython.noop,
        ),
    ]
