from datetime import timedelta
from decimal import Decimal

from django.db.models import F
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.catalog.models import Product
from apps.core.permissions import HasPOSPermission
from apps.core.shop_context import ShopScopedMixin
from apps.core.utils import dict_to_camel_case
from apps.dashboard.services import build_overview
from apps.parties.models import Customer, Supplier
from apps.sales.figures import local_stamp, money_float, recognize_period, shop_zone, start_of_day, totals_from_activity


class DashboardViewSet(ShopScopedMixin, ViewSet):
    permission_classes = [IsAuthenticated, HasPOSPermission]
    required_permission = "DASHBOARD_VIEW"

    def _summary_data(self):
        shop = self.shop
        zone = shop_zone(shop)
        today = timezone.now().astimezone(zone).date()
        today_start = start_of_day(today, zone)
        tomorrow = start_of_day(today + timedelta(days=1), zone)
        month_start = start_of_day(today.replace(day=1), zone)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        month_end = start_of_day(next_month, zone)
        today_totals = totals_from_activity(recognize_period(shop, today_start, tomorrow))
        month_totals = totals_from_activity(recognize_period(shop, month_start, month_end))
        all_totals = totals_from_activity(recognize_period(shop, None, None))

        products = Product.objects.filter(status=True, shop=shop)
        low_stock_count = products.filter(stock_quantity__gt=0, stock_quantity__lte=F("reorder_level")).count()
        out_of_stock_count = products.filter(stock_quantity__lte=0).count()

        return {
            "today_sales": today_totals["revenue"],
            "monthly_sales": month_totals["revenue"],
            "total_revenue": all_totals["revenue"],
            "gross_profit": all_totals["gross_profit"],
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "total_customers": Customer.objects.filter(shop=shop).count(),
            "total_suppliers": Supplier.objects.filter(shop=shop).count(),
        }

    def list(self, request):
        return Response(dict_to_camel_case(self._summary_data()))

    def summary(self, request):
        return Response(dict_to_camel_case(self._summary_data()))

    def sales_trend(self, request):
        shop = self.shop
        zone = shop_zone(shop)
        today = timezone.now().astimezone(zone).date()
        week_start = start_of_day(today - timedelta(days=6), zone)
        tomorrow = start_of_day(today + timedelta(days=1), zone)
        year_start = start_of_day(today.replace(month=1, day=1), zone)
        week = recognize_period(shop, week_start, tomorrow)
        year = recognize_period(shop, year_start, tomorrow)
        daily_totals = _money_by_day(week, zone)
        monthly_totals = _money_by_month(year, zone)
        daily = [
            {"label": day.strftime("%a"), "total": money_float(total)}
            for day, total in sorted(daily_totals.items())
        ]
        monthly = [
            {"label": month.strftime("%b"), "total": money_float(total)}
            for month, total in sorted(monthly_totals.items())
        ]
        return Response({"daily": daily, "monthly": monthly})

    def top_products(self, request):
        activity = recognize_period(self.shop, None, None)
        ranked = sorted(
            _product_totals(activity).values(),
            key=lambda row: row["units"],
            reverse=True,
        )[:10]
        data = [
            {
                "product_id": row["product_id"],
                "name": row["name"],
                "quantity_sold": float(row["units"]),
                "revenue": money_float(row["revenue"]),
            }
            for row in ranked
        ]
        return Response([dict_to_camel_case(item) for item in data])

    def overview(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        if days not in (7, 30, 90):
            days = 30
        return Response(dict_to_camel_case(build_overview(self.shop, days)))

    def sales_by_category(self, request):
        totals = _category_totals(recognize_period(self.shop, None, None))
        data = [
            {"category": name, "total": money_float(total)}
            for name, total in sorted(totals.items(), key=lambda row: row[1], reverse=True)
            if total != 0
        ]
        return Response(data)


def _add_line_totals(bucket, line, sign):
    row = bucket.setdefault(
        line["product_id"],
        {"product_id": line["product_id"], "name": line["name"], "units": Decimal("0"), "revenue": Decimal("0")},
    )
    row["units"] += sign * line["units"]
    money = line["revenue"] if sign > 0 else line["money"]
    row["revenue"] += sign * money


def _product_totals(activity):
    bucket = {}
    for sale in activity["sales"]:
        for line in sale["lines"]:
            _add_line_totals(bucket, line, Decimal("1"))
    for ret in activity["returns"]:
        for line in ret["lines"]:
            _add_line_totals(bucket, line, Decimal("-1"))
    return bucket


def _category_totals(activity):
    totals = {}
    for sale in activity["sales"]:
        for line in sale["lines"]:
            totals[line["category"]] = totals.get(line["category"], Decimal("0")) + line["revenue"]
    for ret in activity["returns"]:
        for line in ret["lines"]:
            totals[line["category"]] = totals.get(line["category"], Decimal("0")) - line["money"]
    return totals


def _money_by_day(activity, zone):
    totals = {}
    for sale in activity["sales"]:
        local = local_stamp(sale["at"], zone)
        if local is not None:
            totals[local.date()] = totals.get(local.date(), Decimal("0")) + sale["money"]
    for ret in activity["returns"]:
        local = local_stamp(ret["at"], zone)
        if local is not None:
            totals[local.date()] = totals.get(local.date(), Decimal("0")) - ret["money"]
    return totals


def _money_by_month(activity, zone):
    totals = {}
    for sale in activity["sales"]:
        local = local_stamp(sale["at"], zone)
        if local is not None:
            key = local.date().replace(day=1)
            totals[key] = totals.get(key, Decimal("0")) + sale["money"]
    for ret in activity["returns"]:
        local = local_stamp(ret["at"], zone)
        if local is not None:
            key = local.date().replace(day=1)
            totals[key] = totals.get(key, Decimal("0")) - ret["money"]
    return totals
