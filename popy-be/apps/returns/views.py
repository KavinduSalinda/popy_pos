from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import HasPOSPermission
from apps.core.shop_context import ShopScopedMixin
from apps.core.utils import dict_to_camel_case
from apps.returns.models import PurchaseReturn, SalesReturn
from apps.returns.serializers import (
    PurchaseReturnCreateSerializer,
    PurchaseReturnSerializer,
    SalesReturnCreateSerializer,
    SalesReturnSerializer,
)
from apps.returns.services import (
    ReturnLookupError,
    create_purchase_return,
    create_sales_return,
    lookup_code,
)


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

    def post(self, request):
        serializer = PurchaseReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            purchase_return = create_purchase_return(
                self.shop,
                purchase_id=data["purchase_id"],
                reason=data["reason"],
                items=data.get("items") or [],
            )
        except ReturnLookupError as exc:
            return Response(
                {"message": exc.message, "statusCode": exc.status_code},
                status=exc.status_code,
            )
        return Response(
            PurchaseReturnSerializer(purchase_return).data,
            status=status.HTTP_201_CREATED,
        )
