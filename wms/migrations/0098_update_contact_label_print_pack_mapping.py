from django.db import migrations


CONTACT_LABEL_MAPPINGS = (
    ("Feuil1", "B3", "shipment.shipper.display_name", "upper", False),
    ("Feuil1", "B4", "shipment.shipper.structure_name", "upper", False),
    ("Feuil1", "B5", "shipment.shipper.postal_address_display", "upper", False),
    ("Feuil1", "B6", "shipment.shipper.email_1", "upper", False),
    ("Feuil1", "B7", "shipment.shipper.phone_1", "upper", False),
    ("Feuil1", "B10", "shipment.recipient.display_name", "upper", False),
    ("Feuil1", "B11", "shipment.recipient.structure_name", "upper", False),
    ("Feuil1", "B12", "shipment.recipient.postal_address_display", "upper", False),
    ("Feuil1", "B13", "shipment.recipient.email_1", "upper", False),
    ("Feuil1", "B14", "shipment.recipient.phone_1", "upper", False),
    ("Feuil1", "B17", "shipment.correspondent.display_name", "upper", False),
    ("Feuil1", "B18", "shipment.correspondent.structure_name", "upper", False),
    ("Feuil1", "B19", "shipment.correspondent.postal_address_display", "upper", False),
    ("Feuil1", "B20", "shipment.correspondent.email_1", "upper", False),
    ("Feuil1", "B21", "shipment.correspondent.phone_1", "upper", False),
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


def update_contact_label_print_pack_mapping(apps, schema_editor):
    del schema_editor

    print_pack_document_model = apps.get_model("wms", "PrintPackDocument")
    print_cell_mapping_model = apps.get_model("wms", "PrintCellMapping")

    pack_document = print_pack_document_model.objects.filter(
        pack__code="C",
        doc_type="contact_label",
        variant="shipment",
    ).first()
    if pack_document is None:
        return

    _sync_document_mappings(
        print_cell_mapping_model,
        pack_document,
        CONTACT_LABEL_MAPPINGS,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0097_update_shipment_note_print_pack_mapping"),
    ]

    operations = [
        migrations.RunPython(
            update_contact_label_print_pack_mapping,
            migrations.RunPython.noop,
        ),
    ]
