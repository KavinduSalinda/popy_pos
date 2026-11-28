from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.core.choices import StockTransactionType
from apps.core.permissions import HasPOSPermission
from apps.core.services import adjust_stock
from apps.core.shop_context import ShopScopedMixin
from apps.core.utils import dict_to_camel_case, generate_reference
from apps.purchasing.models import Purchase
from apps.returns.models import PurchaseReturn, SalesReturn
from apps.returns.serializers import (
    PurchaseReturnCreateSerializer,
    PurchaseReturnSerializer,
    SalesReturnCreateSerializer,
    SalesReturnSerializer,
)
from apps.returns.services import ReturnLookupError, create_sales_return, lookup_code
from apps.sales.models import Sale


def _resolve_shop_document(queryset, lookup: str):
    """Resolve by numeric PK or case-insensitive reference string."""
    value = str(lookup).strip()
    if not value:
        return None
    if value.isdigit():
        return queryset.filter(pk=int(value)).first()
    return queryset.filter(reference__iexact=value).first()


class ReturnViewSet(ShopScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "RETURN_VIEW"

    def list(self, request, *args, **kwargs):
        shop = self.shop
        sales = SalesReturnSerializer(
            SalesReturn.objects.filter(shop=shop).order_by("-created_at")[:50],
            many=True,
        ).data
        purchases = PurchaseReturnSerializer(
            PurchaseReturn.objects.filter(shop=shop).order_by("-created_at")[:50],
            many=True,
        ).data
        combined = sorted(sales + purchases, key=lambda x: x.get("createdAt", ""), reverse=True)
        return Response(combined)


class SalesReturnLookupView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "RETURN_CREATE"

    def get(self, request):
        try:
            payload = lookup_code(self.shop, request.query_params.get("code", ""))
        except ReturnLookupError as exc:
            return Response(
                {"message": exc.message, "statusCode": exc.status_code},
                status=exc.status_code,
            )
        return Response(dict_to_camel_case(payload))


class SalesReturnCreateView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "RETURN_CREATE"

    def post(self, request):
        serializer = SalesReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            sales_return = create_sales_return(
                self.shop,
                code=data.get("code") or "",
                sale_id=data.get("sale_id") or "",
                reason=data["reason"],
                refund_amount=data["refund_amount"],
                items=data.get("items") or [],
                quantity=data.get("quantity"),
            )
        except ReturnLookupError as exc:
            return Response(
                {"message": exc.message, "statusCode": exc.status_code},
                status=exc.status_code,
            )
        return Response(SalesReturnSerializer(sales_return).data, status=status.HTTP_201_CREATED)


class PurchaseReturnCreateView(ShopScopedMixin, APIView):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "RETURN_CREATE"

    @transaction.atomic
    def post(self, request):
        shop = self.shop
        serializer = PurchaseReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        purchase = _resolve_shop_document(
            Purchase.objects.prefetch_related("items__product").filter(shop=shop),
            data["purchase_id"],
        )
        if purchase is None:
            return Response(
                {"message": "Purchase not found", "statusCode": 404},
                status=status.HTTP_404_NOT_FOUND,
            )

        reference = generate_reference("PR", PurchaseReturn, shop=shop)
        items = data.get("items") or []

        if not items:
            for purchase_item in purchase.items.all():
                try:
                    adjust_stock(
                        purchase_item.product,
                        -purchase_item.quantity,
                        StockTransactionType.RETURN,
                        note=f"Purchase return {reference}",
                        reference_type="PurchaseReturn",
                    )
                except ValueError:
                    pass
        else:
            for item in items:
                product_id = item.get("productId") or item.get("product_id")
                quantity = item.get("quantity", 0)
                if product_id and quantity:
                    product = Product.objects.select_for_update().get(pk=product_id, shop=shop)
                    adjust_stock(
                        product,
                        -quantity,
                        StockTransactionType.RETURN,
                        note=f"Purchase return {reference}",
                        reference_type="PurchaseReturn",
                    )

        purchase_return = PurchaseReturn.objects.create(
            shop=shop,
            reference=reference,
            purchase=purchase,
            reason=data["reason"],
            amount=data["amount"],
            items=items,
        )
        return Response(
            PurchaseReturnSerializer(purchase_return).data,
            status=status.HTTP_201_CREATED,
        )
