from django.core.validators import MinValueValidator
from django.db import models


class ShipmentUnitEquivalenceRule(models.Model):
    label = models.CharField(max_length=120)
    category = models.ForeignKey(
        "wms.ProductCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="shipment_unit_equivalence_rules",
    )
    applies_to_hors_format = models.BooleanField(default=False)
    units_per_item = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    priority = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self) -> str:
        return self.label
