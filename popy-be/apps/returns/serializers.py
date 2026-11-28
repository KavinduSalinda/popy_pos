from rest_framework import serializers

from apps.core.serializers import CamelCaseModelSerializer, CamelCaseSerializer
from apps.returns.models import PurchaseReturn, SalesReturn


class SalesReturnSerializer(CamelCaseModelSerializer):
    sale_id = serializers.IntegerField(read_only=True)
    type = serializers.SerializerMethodField()
    amount = serializers.DecimalField(source="refund_amount", read_only=True, max_digits=14, decimal_places=2)

    class Meta:
        model = SalesReturn
        fields = ["id", "reference", "type", "sale_id", "reason", "amount", "refund_amount", "items", "created_at"]

    def get_type(self, obj):
        return "SALES"


class PurchaseReturnSerializer(CamelCaseModelSerializer):
    purchase_id = serializers.IntegerField(read_only=True)
    type = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReturn
        fields = ["id", "reference", "type", "purchase_id", "reason", "amount", "items", "created_at"]

    def get_type(self, obj):
        return "PURCHASE"


class SalesReturnCreateSerializer(CamelCaseSerializer):
    # Bill reference, numeric sale id, barcode, or SKU.
    sale_id = serializers.CharField(required=False, allow_blank=True)
    code = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField()
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    refund_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True
    )

    def validate(self, attrs):
        code = (attrs.get("code") or "").strip()
        sale_id = (attrs.get("sale_id") or "").strip()
        attrs["code"] = code
        attrs["sale_id"] = sale_id
        if not code and not sale_id:
            raise serializers.ValidationError("Enter a bill, barcode, or SKU.")
        return attrs


class PurchaseReturnCreateSerializer(CamelCaseSerializer):
    # Numeric purchase id or human reference (e.g. PO-2026-0001)
    purchase_id = serializers.CharField()
    reason = serializers.CharField()
    items = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
