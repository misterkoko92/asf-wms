import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wms.models import Location, Product, ProductCategory, ProductTag, Warehouse

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover - optional dependency at runtime
    load_workbook = None


TRUE_VALUES = {"true", "1", "yes", "y", "oui", "o", "vrai"}
FALSE_VALUES = {"false", "0", "no", "n", "non", "faux"}


def normalize_header(value: str) -> str:
    return value.strip().lower()


def parse_str(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise CommandError(f"Invalid decimal value: {value}") from exc


def parse_int(value):
    decimal_value = parse_decimal(value)
    if decimal_value is None:
        return None
    return int(decimal_value.to_integral_value(rounding=ROUND_HALF_UP))


def parse_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise CommandError(f"Invalid boolean value: {value}")


def build_category_path(parts):
    parent = None
    for name in parts:
        if not name:
            continue
        category, _ = ProductCategory.objects.get_or_create(name=name, parent=parent)
        parent = category
    return parent


def build_tags(raw_value):
    if not raw_value:
        return [], False
    tags = []
    for token in raw_value.split("|"):
        name = token.strip()
        if not name:
            continue
        tag, _ = ProductTag.objects.get_or_create(name=name)
        tags.append(tag)
    return tags, True


def get_or_create_location(warehouse_name, zone, aisle, shelf, row_number, stderr):
    if not any([warehouse_name, zone, aisle, shelf]):
        return None
    if not all([warehouse_name, zone, aisle, shelf]):
        stderr.write(
            f"Row {row_number}: incomplete location (warehouse/zone/aisle/shelf)."
        )
        return None
    warehouse, _ = Warehouse.objects.get_or_create(name=warehouse_name)
    location, _ = Location.objects.get_or_create(
        warehouse=warehouse, zone=zone, aisle=aisle, shelf=shelf
    )
    return location


def compute_volume(length_cm, width_cm, height_cm):
    if length_cm is None or width_cm is None or height_cm is None:
        return None
    volume = length_cm * width_cm * height_cm
    return int(volume.to_integral_value(rounding=ROUND_HALF_UP))


def iter_csv_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            normalized = {normalize_header(k): v for k, v in row.items() if k}
            yield normalized


def iter_excel_rows(path):
    if load_workbook is None:
        raise CommandError("openpyxl is required to import Excel files.")
    workbook = load_workbook(path, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        headers = next(rows)
    except StopIteration as exc:
        raise CommandError("Excel file is empty.") from exc
    normalized_headers = [normalize_header(str(h or "")) for h in headers]
    for row in rows:
        data = {}
        for header, value in zip(normalized_headers, row):
            if not header:
                continue
            data[header] = value
        yield data


class Command(BaseCommand):
    help = "Import products from CSV or Excel."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to CSV or XLSX file")
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing products when SKU already exists",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate import without writing to the database",
        )
        parser.add_argument(
            "--skip-errors",
            action="store_true",
            help="Continue on row errors",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        if path.suffix.lower() in {".xlsx", ".xlsm"}:
            rows = iter_excel_rows(path)
        else:
            rows = iter_csv_rows(path)

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        with transaction.atomic():
            for index, row in enumerate(rows, start=2):
                try:
                    sku = parse_str(row.get("sku"))
                    name = parse_str(row.get("name"))
                    if not name:
                        raise CommandError("Missing required field: name")
                    if options["update"] and not sku:
                        raise CommandError("Missing required field for update: sku")

                    product = Product.objects.filter(sku=sku).first() if sku else None
                    if product and not options["update"]:
                        skipped += 1
                        continue

                    category_parts = [
                        parse_str(row.get("category_l1")),
                        parse_str(row.get("category_l2")),
                        parse_str(row.get("category_l3")),
                        parse_str(row.get("category_l4")),
                    ]
                    category = build_category_path([p for p in category_parts if p])
                    category_provided = any(category_parts)

                    tags, tags_provided = build_tags(parse_str(row.get("tags")))

                    warehouse_name = parse_str(row.get("warehouse"))
                    zone = parse_str(row.get("zone"))
                    aisle = parse_str(row.get("aisle"))
                    shelf = parse_str(row.get("shelf"))
                    default_location = get_or_create_location(
                        warehouse_name, zone, aisle, shelf, index, self.stderr
                    )
                    location_provided = default_location is not None

                    barcode = parse_str(row.get("barcode"))
                    brand = parse_str(row.get("brand"))
                    length_cm = parse_decimal(row.get("length_cm"))
                    width_cm = parse_decimal(row.get("width_cm"))
                    height_cm = parse_decimal(row.get("height_cm"))
                    weight_g = parse_int(row.get("weight_g"))
                    volume_cm3 = parse_int(row.get("volume_cm3"))
                    if volume_cm3 is None:
                        computed = compute_volume(length_cm, width_cm, height_cm)
                        volume_cm3 = computed

                    storage_conditions = parse_str(row.get("storage_conditions"))
                    perishable = parse_bool(row.get("perishable"))
                    quarantine_default = parse_bool(row.get("quarantine_default"))
                    notes = parse_str(row.get("notes"))

                    if product is None:
                        product = Product(sku=sku or "", name=name)
                        if category is not None:
                            product.category = category
                        if barcode is not None:
                            product.barcode = barcode
                        if brand is not None:
                            product.brand = brand
                        if location_provided:
                            product.default_location = default_location
                        if length_cm is not None:
                            product.length_cm = length_cm
                        if width_cm is not None:
                            product.width_cm = width_cm
                        if height_cm is not None:
                            product.height_cm = height_cm
                        if weight_g is not None:
                            product.weight_g = weight_g
                        if volume_cm3 is not None:
                            product.volume_cm3 = volume_cm3
                        if storage_conditions is not None:
                            product.storage_conditions = storage_conditions
                        if perishable is not None:
                            product.perishable = perishable
                        if quarantine_default is not None:
                            product.quarantine_default = quarantine_default
                        if notes is not None:
                            product.notes = notes
                        product.save()
                        if tags_provided:
                            product.tags.set(tags)
                        created += 1
                        continue

                    updates = {}
                    if name is not None:
                        updates["name"] = name
                    if category_provided:
                        updates["category"] = category
                    if barcode is not None:
                        updates["barcode"] = barcode
                    if brand is not None:
                        updates["brand"] = brand
                    if location_provided:
                        updates["default_location"] = default_location
                    if length_cm is not None:
                        updates["length_cm"] = length_cm
                    if width_cm is not None:
                        updates["width_cm"] = width_cm
                    if height_cm is not None:
                        updates["height_cm"] = height_cm
                    if weight_g is not None:
                        updates["weight_g"] = weight_g
                    if volume_cm3 is not None:
                        updates["volume_cm3"] = volume_cm3
                    if storage_conditions is not None:
                        updates["storage_conditions"] = storage_conditions
                    if perishable is not None:
                        updates["perishable"] = perishable
                    if quarantine_default is not None:
                        updates["quarantine_default"] = quarantine_default
                    if notes is not None:
                        updates["notes"] = notes

                    if updates:
                        for field, value in updates.items():
                            setattr(product, field, value)
                        product.save(update_fields=list(updates.keys()))
                    if tags_provided:
                        product.tags.set(tags)
                    updated += 1
                except CommandError as exc:
                    errors += 1
                    if options["skip_errors"]:
                        self.stderr.write(f"Row {index}: {exc}")
                        continue
                    raise

            if options["dry_run"]:
                transaction.set_rollback(True)

        summary = (
            f"Imported products: created={created}, updated={updated}, "
            f"skipped={skipped}, errors={errors}"
        )
        if options["dry_run"]:
            summary += " (dry-run)"
        self.stdout.write(summary)
