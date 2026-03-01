from django.db import migrations


PACK_DEFAULTS = (
    {
        "code": "A",
        "name": "Pack A - Picking",
        "description": "Picking par carton (format standard).",
        "active": True,
        "default_page_format": "A4",
        "fallback_page_format": None,
    },
    {
        "code": "B",
        "name": "Pack B - Colisage + Donation",
        "description": "Liste de colisage + attestation de donation.",
        "active": True,
        "default_page_format": "A5",
        "fallback_page_format": "A4",
    },
    {
        "code": "C",
        "name": "Pack C - Expedition + Contact",
        "description": "Bon d'expedition + etiquette contact.",
        "active": True,
        "default_page_format": "A5",
        "fallback_page_format": "A4",
    },
    {
        "code": "D",
        "name": "Pack D - Etiquette Destination",
        "description": "Etiquette destination.",
        "active": True,
        "default_page_format": "A5",
        "fallback_page_format": None,
    },
)


PACK_DOCUMENT_DEFAULTS = (
    {
        "pack_code": "A",
        "doc_type": "picking",
        "variant": "single_carton",
        "sequence": 1,
        "enabled": True,
    },
    {
        "pack_code": "B",
        "doc_type": "packing_list_shipment",
        "variant": "shipment",
        "sequence": 1,
        "enabled": True,
    },
    {
        "pack_code": "B",
        "doc_type": "donation_certificate",
        "variant": "shipment",
        "sequence": 2,
        "enabled": True,
    },
    {
        "pack_code": "B",
        "doc_type": "packing_list_carton",
        "variant": "per_carton_single",
        "sequence": 1,
        "enabled": True,
    },
    {
        "pack_code": "C",
        "doc_type": "shipment_note",
        "variant": "shipment",
        "sequence": 1,
        "enabled": True,
    },
    {
        "pack_code": "C",
        "doc_type": "contact_label",
        "variant": "shipment",
        "sequence": 2,
        "enabled": True,
    },
    {
        "pack_code": "D",
        "doc_type": "destination_label",
        "variant": "all_labels",
        "sequence": 1,
        "enabled": True,
    },
    {
        "pack_code": "D",
        "doc_type": "destination_label",
        "variant": "single_label",
        "sequence": 1,
        "enabled": True,
    },
)


def seed_default_print_pack_configuration(apps, schema_editor):
    del schema_editor

    PrintPack = apps.get_model("wms", "PrintPack")
    PrintPackDocument = apps.get_model("wms", "PrintPackDocument")

    packs_by_code = {}
    for config in PACK_DEFAULTS:
        pack, created = PrintPack.objects.get_or_create(
            code=config["code"],
            defaults={
                "name": config["name"],
                "description": config["description"],
                "active": config["active"],
                "default_page_format": config["default_page_format"],
                "fallback_page_format": config["fallback_page_format"],
            },
        )
        if not created:
            update_fields = []
            for field in (
                "name",
                "description",
                "active",
                "default_page_format",
                "fallback_page_format",
            ):
                value = config[field]
                if getattr(pack, field) != value:
                    setattr(pack, field, value)
                    update_fields.append(field)
            if update_fields:
                pack.save(update_fields=update_fields)
        packs_by_code[config["code"]] = pack

    for config in PACK_DOCUMENT_DEFAULTS:
        pack = packs_by_code[config["pack_code"]]
        document, created = PrintPackDocument.objects.get_or_create(
            pack=pack,
            doc_type=config["doc_type"],
            variant=config["variant"],
            defaults={
                "sequence": config["sequence"],
                "enabled": config["enabled"],
            },
        )
        if not created:
            update_fields = []
            for field in ("sequence", "enabled"):
                value = config[field]
                if getattr(document, field) != value:
                    setattr(document, field, value)
                    update_fields.append(field)
            if update_fields:
                document.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("wms", "0060_generatedprintartifact_printpack_printpackdocument_and_more"),
    ]

    operations = [
        migrations.RunPython(
            seed_default_print_pack_configuration,
            migrations.RunPython.noop,
        ),
    ]
