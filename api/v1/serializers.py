from rest_framework import serializers

from wms.models import (
    Destination,
    IntegrationEvent,
    Order,
    OrderLine,
    OrderReviewStatus,
    Product,
    ProductLotStatus,
    Shipment,
    ShipmentTrackingStatus,
)


class ProductSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(read_only=True)
    category_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "brand",
            "color",
            "category_id",
            "category_name",
            "tags",
            "barcode",
            "ean",
            "pu_ht",
            "tva",
            "pu_ttc",
            "available_stock",
            "default_location_id",
            "storage_conditions",
            "perishable",
            "quarantine_default",
            "notes",
            "is_active",
            "weight_g",
            "volume_cm3",
            "length_cm",
            "width_cm",
            "height_cm",
            "photo",
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


class UiStockUpdateSerializer(serializers.Serializer):
    product_code = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    expires_on = serializers.DateField()
    lot_code = serializers.CharField(required=False, allow_blank=True, default="")
    donor_contact_id = serializers.IntegerField(required=False, allow_null=True)


class UiStockOutSerializer(serializers.Serializer):
    product_code = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    shipment_reference = serializers.CharField(required=False, allow_blank=True, default="")
    reason_code = serializers.CharField(required=False, allow_blank=True, default="")
    reason_notes = serializers.CharField(required=False, allow_blank=True, default="")


class UiOrderReviewStatusSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(choices=OrderReviewStatus.choices)


class UiScanOrderCreateSerializer(serializers.Serializer):
    shipper_name = serializers.CharField()
    recipient_name = serializers.CharField()
    correspondent_name = serializers.CharField(required=False, allow_blank=True, default="")
    shipper_contact_id = serializers.IntegerField(required=False, allow_null=True)
    recipient_contact_id = serializers.IntegerField(required=False, allow_null=True)
    correspondent_contact_id = serializers.IntegerField(required=False, allow_null=True)
    destination_address = serializers.CharField()
    destination_city = serializers.CharField(required=False, allow_blank=True, default="")
    destination_country = serializers.CharField(required=False, allow_blank=True, default="France")
    requested_delivery_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class UiScanOrderAddLineSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    product_code = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)


class UiScanOrderPrepareSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class UiShipmentLineSerializer(serializers.Serializer):
    carton_id = serializers.IntegerField(required=False, allow_null=True)
    product_code = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        carton_id = attrs.get("carton_id")
        product_code = (attrs.get("product_code") or "").strip()
        quantity = attrs.get("quantity")
        if carton_id and (product_code or quantity):
            raise serializers.ValidationError(
                "Choisissez un carton OU creez un colis depuis un produit."
            )
        if carton_id:
            return attrs
        if product_code and quantity and quantity > 0:
            return attrs
        raise serializers.ValidationError(
            "Chaque ligne doit contenir un carton_id ou le couple product_code + quantity."
        )


class UiShipmentMutationSerializer(serializers.Serializer):
    destination = serializers.IntegerField()
    shipper_contact = serializers.IntegerField()
    recipient_contact = serializers.IntegerField()
    correspondent_contact = serializers.IntegerField()
    lines = UiShipmentLineSerializer(many=True, min_length=1)


class UiShipmentTrackingEventSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ShipmentTrackingStatus.choices)
    actor_name = serializers.CharField(max_length=120)
    actor_structure = serializers.CharField(max_length=120)
    comments = serializers.CharField(required=False, allow_blank=True, default="")


class UiPortalOrderLineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class UiPortalOrderCreateSerializer(serializers.Serializer):
    destination_id = serializers.IntegerField()
    recipient_id = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = UiPortalOrderLineSerializer(many=True, min_length=1)


class UiPortalRecipientMutationSerializer(serializers.Serializer):
    destination_id = serializers.IntegerField()
    structure_name = serializers.CharField()
    contact_title = serializers.CharField(required=False, allow_blank=True, default="")
    contact_last_name = serializers.CharField(required=False, allow_blank=True, default="")
    contact_first_name = serializers.CharField(required=False, allow_blank=True, default="")
    phones = serializers.CharField(required=False, allow_blank=True, default="")
    emails = serializers.CharField(required=False, allow_blank=True, default="")
    address_line1 = serializers.CharField()
    address_line2 = serializers.CharField(required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(required=False, allow_blank=True, default="")
    country = serializers.CharField(required=False, allow_blank=True, default="France")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    notify_deliveries = serializers.BooleanField(required=False, default=False)
    is_delivery_contact = serializers.BooleanField(required=False, default=False)


class UiPortalAccountContactSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    is_administrative = serializers.BooleanField(required=False, default=False)
    is_shipping = serializers.BooleanField(required=False, default=False)
    is_billing = serializers.BooleanField(required=False, default=False)


class UiPortalAccountUpdateSerializer(serializers.Serializer):
    association_name = serializers.CharField()
    association_email = serializers.EmailField(required=False, allow_blank=True, default="")
    association_phone = serializers.CharField(required=False, allow_blank=True, default="")
    address_line1 = serializers.CharField()
    address_line2 = serializers.CharField(required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(required=False, allow_blank=True, default="")
    country = serializers.CharField(required=False, allow_blank=True, default="France")
    contacts = UiPortalAccountContactSerializer(many=True, min_length=1)


class UiPrintTemplateMutationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=(
            ("save", "save"),
            ("reset", "reset"),
        ),
        required=False,
        default="save",
    )
    layout = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        action = attrs.get("action", "save")
        layout = attrs.get("layout", {})
        if action == "reset":
            attrs["layout"] = {}
            return attrs
        if not isinstance(layout, dict):
            raise serializers.ValidationError(
                {"layout": ["Le layout doit etre un objet JSON."]}
            )
        attrs["layout"] = layout
        return attrs
