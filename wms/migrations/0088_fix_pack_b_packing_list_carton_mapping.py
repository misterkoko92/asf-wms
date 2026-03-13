from django.db import migrations


def fix_pack_b_packing_list_carton_mapping(apps, schema_editor):
    del schema_editor

    print_pack_document_model = apps.get_model("wms", "PrintPackDocument")
    print_cell_mapping_model = apps.get_model("wms", "PrintCellMapping")

    pack_document = print_pack_document_model.objects.filter(
        pack__code="B",
        doc_type="packing_list_carton",
        variant="per_carton_single",
    ).first()
    if pack_document is None:
        return

    mapping = print_cell_mapping_model.objects.filter(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        source_key="carton.code",
    ).first()
    defaults = {
        "source_key": "carton.code",
        "transform": "",
        "required": True,
        "sequence": getattr(mapping, "sequence", 1),
    }
    print_cell_mapping_model.objects.update_or_create(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        cell_ref="B9",
        defaults=defaults,
    )
    print_cell_mapping_model.objects.filter(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        cell_ref="B10",
        source_key="carton.code",
    ).delete()


def unfix_pack_b_packing_list_carton_mapping(apps, schema_editor):
    del schema_editor

    print_pack_document_model = apps.get_model("wms", "PrintPackDocument")
    print_cell_mapping_model = apps.get_model("wms", "PrintCellMapping")

    pack_document = print_pack_document_model.objects.filter(
        pack__code="B",
        doc_type="packing_list_carton",
        variant="per_carton_single",
    ).first()
    if pack_document is None:
        return

    mapping = print_cell_mapping_model.objects.filter(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        source_key="carton.code",
    ).first()
    defaults = {
        "source_key": "carton.code",
        "transform": "",
        "required": True,
        "sequence": getattr(mapping, "sequence", 1),
    }
    print_cell_mapping_model.objects.update_or_create(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        cell_ref="B10",
        defaults=defaults,
    )
    print_cell_mapping_model.objects.filter(
        pack_document=pack_document,
        worksheet_name="Feuil1",
        cell_ref="B9",
        source_key="carton.code",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0087_communicationdraft_family"),
    ]

    operations = [
        migrations.RunPython(
            fix_pack_b_packing_list_carton_mapping,
            unfix_pack_b_packing_list_carton_mapping,
        ),
    ]
