from django.core.management.base import BaseCommand

from wms.models import Location, Product, ProductCategory, RackColor
from wms.text_utils import normalize_category_name, normalize_title, normalize_upper


class Command(BaseCommand):
    help = "Normalize casing for products, categories, and locations."

    def handle(self, *args, **options):
        product_updates = 0
        for product in Product.objects.all():
            fields = []
            if product.name:
                normalized = normalize_title(product.name)
                if normalized != product.name:
                    product.name = normalized
                    fields.append("name")
            if product.brand:
                normalized = normalize_upper(product.brand)
                if normalized != product.brand:
                    product.brand = normalized
                    fields.append("brand")
            if fields:
                product.save(update_fields=fields)
                product_updates += 1

        category_updates = 0
        for category in ProductCategory.objects.all():
            if not category.name:
                continue
            normalized = normalize_category_name(category.name)
            if normalized != category.name:
                category.name = normalized
                category.save(update_fields=["name"])
                category_updates += 1

        location_updates = 0
        for location in Location.objects.all():
            fields = []
            if location.zone:
                normalized = normalize_upper(location.zone)
                if normalized != location.zone:
                    location.zone = normalized
                    fields.append("zone")
            if location.aisle:
                normalized = normalize_upper(location.aisle)
                if normalized != location.aisle:
                    location.aisle = normalized
                    fields.append("aisle")
            if location.shelf:
                normalized = normalize_upper(location.shelf)
                if normalized != location.shelf:
                    location.shelf = normalized
                    fields.append("shelf")
            if fields:
                location.save(update_fields=fields)
                location_updates += 1

        rack_updates = 0
        for rack in RackColor.objects.all():
            if not rack.zone:
                continue
            normalized = normalize_upper(rack.zone)
            if normalized != rack.zone:
                rack.zone = normalized
                rack.save(update_fields=["zone"])
                rack_updates += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Normalize done: "
                f"products={product_updates}, "
                f"categories={category_updates}, "
                f"locations={location_updates}, "
                f"rack_colors={rack_updates}."
            )
        )
