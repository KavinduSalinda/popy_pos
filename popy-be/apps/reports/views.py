from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.catalog.models import Product
from apps.core.permissions import HasPOSPermission
from apps.core.shop_context import ShopScopedMixin
from apps.parties.models import Customer
from apps.purchasing.models import Purchase
from apps.sales.figures import local_stamp, money_float, recognize_period, shop_zone


def parse_date_range(request):
    from_date = request.query_params.get("fromDate") or request.query_params.get("from_date")
    to_date = request.query_params.get("toDate") or request.query_params.get("to_date")
    start = None
    end = timezone.now()
    if from_date:
        start = timezone.make_aware(datetime.fromisoformat(from_date.replace("Z", "")))
    if to_date:
        end = timezone.make_aware(datetime.fromisoformat(to_date.replace("Z", "")))
    return start, end


class ReportViewSet(ShopScopedMixin, ViewSet):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "REPORT_VIEW"

    def sales(self, request):
        start, end = parse_date_range(request)
        activity = recognize_period(self.shop, start, end, inclusive_end=True)
        zone = shop_zone(self.shop)
        totals = _signed_by_day(activity, zone, "money")
        rows = [
            {"date": day.isoformat(), "total": money_float(total)}
            for day, total in sorted(totals.items())
        ]
        return Response(
            {
                "columns": [
                    {"field": "date", "header": "Date", "type": "date"},
                    {"field": "total", "header": "Total", "type": "currency"},
                ],
                "rows": rows,
                "summary": {"grandTotal": money_float(sum(totals.values(), Decimal("0")))},
            }
        )

    def inventory(self, request):
        products = Product.objects.select_related("category").filter(shop=self.shop)
        rows = [
            {
                "product": p.name,
                "sku": p.sku,
                "stock": p.stock_quantity,
                "value": float(p.stock_quantity * p.cost_price),
            }
            for p in products
        ]
        grand_total = sum(r["value"] for r in rows)
        return Response(
            {
                "columns": [
                    {"field": "product", "header": "Product", "type": "text"},
                    {"field": "sku", "header": "SKU", "type": "text"},
                    {"field": "stock", "header": "Stock", "type": "number"},
                    {"field": "value", "header": "Value", "type": "currency"},
                ],
                "rows": rows,
                "summary": {"grandTotal": grand_total},
            }
        )

    def purchases(self, request):
        start, end = parse_date_range(request)
        qs = Purchase.objects.filter(shop=self.shop)
        if start:
            qs = qs.filter(created_at__gte=start)
        qs = qs.filter(created_at__lte=end)

        rows = [
            {
                "reference": p.reference,
                "supplier": p.supplier.name,
                "total": float(p.total),
                "date": p.created_at.date().isoformat(),
            }
            for p in qs
        ]
        grand_total = float(qs.aggregate(t=Sum("total"))["t"] or 0)
        return Response(
            {
                "columns": [
                    {"field": "reference", "header": "Reference", "type": "text"},
                    {"field": "supplier", "header": "Supplier", "type": "text"},
                    {"field": "total", "header": "Total", "type": "currency"},
                    {"field": "date", "header": "Date", "type": "date"},
                ],
                "rows": rows,
                "summary": {"grandTotal": grand_total},
            }
        )

    def customers(self, request):
        activity = recognize_period(self.shop, None, None)
        totals = {}
        for sale in activity["sales"]:
            if sale["customer_id"] is None:
                continue
            totals[sale["customer_id"]] = totals.get(sale["customer_id"], Decimal("0")) + sale["money"]
        for ret in activity["returns"]:
            if ret["customer_id"] is None:
                continue
            totals[ret["customer_id"]] = totals.get(ret["customer_id"], Decimal("0")) - ret["money"]
        customers = Customer.objects.filter(shop=self.shop)
        rows = [
            {
                "name": c.name,
                "phone": c.phone,
                "loyaltyPoints": c.loyalty_points,
                "salesTotal": money_float(totals.get(c.id, Decimal("0"))),
            }
            for c in customers
        ]
        return Response(
            {
                "columns": [
                    {"field": "name", "header": "Name", "type": "text"},
                    {"field": "phone", "header": "Phone", "type": "text"},
                    {"field": "loyaltyPoints", "header": "Loyalty Points", "type": "number"},
                    {"field": "salesTotal", "header": "Sales Total", "type": "currency"},
                ],
                "rows": rows,
                "summary": {"grandTotal": sum(r["salesTotal"] for r in rows)},
            }
        )

    def profit(self, request):
        start, end = parse_date_range(request)
        activity = recognize_period(self.shop, start, end, inclusive_end=True)
        zone = shop_zone(self.shop)
        totals = _signed_by_day(activity, zone, "profit")
        rows = [
            {"date": day.isoformat(), "profit": money_float(total)}
            for day, total in sorted(totals.items())
        ]
        return Response(
            {
                "columns": [
                    {"field": "date", "header": "Date", "type": "date"},
                    {"field": "profit", "header": "Profit", "type": "currency"},
                ],
                "rows": rows,
                "summary": {"grandTotal": money_float(sum(totals.values(), Decimal("0")))},
            }
        )


def _signed_by_day(activity, zone, field):
    totals = {}
    for sale in activity["sales"]:
        local = local_stamp(sale["at"], zone)
        if local is None:
            continue
        totals[local.date()] = totals.get(local.date(), Decimal("0")) + sale[field]
    for ret in activity["returns"]:
        local = local_stamp(ret["at"], zone)
        if local is None:
            continue
        totals[local.date()] = totals.get(local.date(), Decimal("0")) - ret[field]
    return totals
