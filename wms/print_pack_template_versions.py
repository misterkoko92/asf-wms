from os.path import basename

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from .models import PrintCellMapping, PrintPackDocumentVersion


def _snapshot_mappings(pack_document):
    snapshot = []
    for mapping in pack_document.cell_mappings.order_by("sequence", "id"):
        snapshot.append(
            {
                "worksheet_name": mapping.worksheet_name,
                "cell_ref": mapping.cell_ref,
                "source_key": mapping.source_key,
                "transform": mapping.transform or "",
                "required": bool(mapping.required),
                "sequence": mapping.sequence,
            }
        )
    return snapshot


def _next_version_number(pack_document):
    latest = (
        pack_document.versions.aggregate(max_version=Max("version"))["max_version"] or 0
    )
    return latest + 1


def _build_snapshot_filename(pack_document, version_number):
    pack_code = (getattr(getattr(pack_document, "pack", None), "code", "") or "").strip()
    doc_type = (getattr(pack_document, "doc_type", "") or "").strip()
    variant = (getattr(pack_document, "variant", "") or "").strip() or "default"
    return f"{pack_code}__{doc_type}__{variant}__v{version_number}.xlsx"


def save_print_pack_document_snapshot(
    *,
    pack_document,
    created_by=None,
    change_type="save",
    change_note="",
):
    version_number = _next_version_number(pack_document)
    version = PrintPackDocumentVersion(
        pack_document=pack_document,
        version=version_number,
        mappings_snapshot=_snapshot_mappings(pack_document),
        change_type=change_type,
        change_note=(change_note or "").strip(),
        created_by=created_by,
    )
    if pack_document.xlsx_template_file:
        with pack_document.xlsx_template_file.open("rb") as stream:
            payload = stream.read()
        version.xlsx_template_file.save(
            _build_snapshot_filename(pack_document, version_number),
            ContentFile(payload),
            save=False,
        )
    version.save()
    return version


def _apply_mappings_snapshot(*, pack_document, mappings_snapshot):
    pack_document.cell_mappings.all().delete()
    create_buffer = []
    for sequence, mapping in enumerate(mappings_snapshot or [], start=1):
        create_buffer.append(
            PrintCellMapping(
                pack_document=pack_document,
                worksheet_name=(mapping.get("worksheet_name") or "").strip(),
                cell_ref=(mapping.get("cell_ref") or "").strip(),
                source_key=(mapping.get("source_key") or "").strip(),
                transform=(mapping.get("transform") or "").strip(),
                required=bool(mapping.get("required", False)),
                sequence=int(mapping.get("sequence") or sequence),
            )
        )
    if create_buffer:
        PrintCellMapping.objects.bulk_create(create_buffer)


def restore_print_pack_document_version(*, version, created_by=None, change_note=""):
    pack_document = version.pack_document
    with transaction.atomic():
        if version.xlsx_template_file:
            with version.xlsx_template_file.open("rb") as stream:
                payload = stream.read()
            snapshot_name = basename(version.xlsx_template_file.name or "") or "template.xlsx"
            pack_document.xlsx_template_file.save(
                snapshot_name,
                ContentFile(payload),
                save=False,
            )
            pack_document.save(update_fields=["xlsx_template_file"])
        else:
            pack_document.xlsx_template_file = None
            pack_document.save(update_fields=["xlsx_template_file"])

        _apply_mappings_snapshot(
            pack_document=pack_document,
            mappings_snapshot=version.mappings_snapshot,
        )
        return save_print_pack_document_snapshot(
            pack_document=pack_document,
            created_by=created_by,
            change_type="restore",
            change_note=change_note,
        )
