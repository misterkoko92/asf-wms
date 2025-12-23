from rest_framework import serializers

from wms.models import Order, OrderLine, Product, ProductLotStatus


class ProductSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "brand",
            "barcode",
            "available_stock",
            "default_location_id",
            "storage_conditions",
            "weight_g",
            "volume_cm3",
            "length_cm",
            "width_cm",
            "height_cm",
        )


class OrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderLine
        fields = (
            "id",
            "product_id",
            "product_name",
            "quantity",
            "reserved_quantity",
            "prepared_quantity",
        )


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "reference",
            "status",
            "shipper_name",
            "recipient_name",
            "correspondent_name",
            "destination_address",
            "destination_city",
            "destination_country",
            "requested_delivery_date",
            "shipment_id",
            "created_at",
            "lines",
        )


class ReceiveStockSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    location_id = serializers.IntegerField()
    lot_code = serializers.CharField(required=False, allow_blank=True)
    received_on = serializers.DateField(required=False, allow_null=True)
    expires_on = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=ProductLotStatus.choices,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    storage_conditions = serializers.CharField(required=False, allow_blank=True)
    source_receipt_id = serializers.IntegerField(required=False, allow_null=True)


class PackCartonSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    carton_id = serializers.IntegerField(required=False, allow_null=True)
    carton_code = serializers.CharField(required=False, allow_blank=True)
    shipment_id = serializers.IntegerField(required=False, allow_null=True)
    current_location_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("carton_id") and attrs.get("carton_code"):
            raise serializers.ValidationError("Choisissez carton_id ou carton_code.")
        return attrs
