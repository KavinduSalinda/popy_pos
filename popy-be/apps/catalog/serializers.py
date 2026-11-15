from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Category, Product
from apps.core.choices import StockTransactionType
from apps.core.serializers import CamelCaseModelSerializer
from apps.core.services import adjust_stock


class CategorySerializer(CamelCaseModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "product_count", "created_at", "updated_at"]


class ProductSerializer(CamelCaseModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all()
    )
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "barcode",
            "category_id",
            "category_name",
            "brand",
            "unit",
            "cost_price",
            "selling_price",
            "reorder_level",
            "stock_quantity",
            "status",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "stock_quantity": {"min_value": Decimal("0")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        shop = self.context.get("shop")
        if shop is not None:
            self.fields["category_id"].queryset = Category.objects.filter(shop=shop)

    def create(self, validated_data):
        stock = validated_data.pop("stock_quantity", Decimal("0")) or Decimal("0")
        with transaction.atomic():
            product = super().create(validated_data)
            self._set_stock(product, stock, opening=True)
        return product

    def update(self, instance, validated_data):
        stock = validated_data.pop("stock_quantity", None)
        with transaction.atomic():
            product = super().update(instance, validated_data)
            if stock is not None:
                self._set_stock(product, stock, opening=False)
        return product

    def _set_stock(self, product: Product, target, *, opening: bool) -> None:
        target = Decimal(str(target)).quantize(Decimal("0.001"))
        if target < 0:
            raise ValidationError({"stock_quantity": "Must be 0 or more."})
        delta = target - Decimal(product.stock_quantity)
        if delta == 0:
            return
        try:
            adjust_stock(
                product,
                delta,
                StockTransactionType.ADJUSTMENT,
                note="Opening stock" if opening else "Stock updated from product form",
                reference_type="Product",
                reference_id=product.id,
            )
        except ValueError as exc:
            raise ValidationError({"stock_quantity": str(exc)}) from exc


class PosProductSerializer(CamelCaseModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "barcode",
            "unit",
            "selling_price",
            "stock_quantity",
            "category_name",
        ]
