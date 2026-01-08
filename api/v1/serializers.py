from rest_framework import serializers

from wms.models import (
    Destination,
    IntegrationEvent,
    Order,
    OrderLine,
    Product,
    ProductLotStatus,
    Shipment,
)


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


class IntegrationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationEvent
        fields = (
            "id",
            "direction",
            "source",
            "target",
            "event_type",
            "external_id",
            "payload",
            "status",
            "error_message",
            "created_at",
            "processed_at",
        )
        read_only_fields = (
            "id",
            "direction",
            "status",
            "error_message",
            "created_at",
            "processed_at",
        )
        extra_kwargs = {
            "source": {"required": False},
            "target": {"required": False},
        }


class IntegrationEventStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationEvent
        fields = ("status", "error_message", "processed_at")


class IntegrationShipmentSerializer(serializers.ModelSerializer):
    destination_iata = serializers.CharField(source="destination.iata_code", allow_null=True)
    destination_city = serializers.CharField(source="destination.city", allow_null=True)
    destination_country = serializers.CharField(source="destination.country", allow_null=True)
    carton_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Shipment
        fields = (
            "id",
            "reference",
            "status",
            "shipper_name",
            "shipper_contact",
            "recipient_name",
            "recipient_contact",
            "correspondent_name",
            "destination_id",
            "destination_iata",
            "destination_city",
            "destination_country",
            "destination_address",
            "requested_delivery_date",
            "created_at",
            "ready_at",
            "notes",
            "carton_count",
        )


class IntegrationDestinationSerializer(serializers.ModelSerializer):
    correspondent_name = serializers.CharField(
        source="correspondent_contact.name", allow_null=True
    )

    class Meta:
        model = Destination
        fields = (
            "id",
            "city",
            "iata_code",
            "country",
            "correspondent_name",
            "is_active",
        )
