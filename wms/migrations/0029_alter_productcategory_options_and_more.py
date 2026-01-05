from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("wms", "0028_product_label_fields"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="productcategory",
            options={
                "ordering": ["name"],
                "verbose_name": "Product category",
                "verbose_name_plural": "Product categories",
            },
        ),
        migrations.AlterModelOptions(
            name="productlot",
            options={
                "ordering": ["product", "expires_on"],
                "verbose_name": "Product Availability",
                "verbose_name_plural": "Product Availability",
            },
        ),
        migrations.AlterModelOptions(
            name="producttag",
            options={
                "ordering": ["name"],
                "verbose_name": "Product",
                "verbose_name_plural": "Product List",
            },
        ),
    ]
