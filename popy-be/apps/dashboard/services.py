"""Aggregations for the dashboard overview."""

from datetime import datetime, time, timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.catalog.models import Product
from apps.returns.models import SalesReturn
from apps.sales.figures import money_float, period_totals
from apps.sales.models import Sale, SaleItem

MONEY = DecimalField(max_digits=16, decimal_places=2)
ZERO = Value(Decimal("0"), output_field=MONEY)

PAYMENT_LABELS = {
    "CASH": "Cash",
    "CARD": "Card",
    "MOBILE": "Mobile",
    "CREDIT": "Credit",
}
PAYMENT_ORDER = ("CASH", "CARD", "MOBILE", "CREDIT")


def _money(value) -> float:
    return money_float(value)


def _shop_zone(shop):
    name = (getattr(shop, "timezone", None) or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _local_stamp(value, zone):
    if value is None:
        return None
    if timezone.is_aware(value):
        return value.astimezone(zone)
    return timezone.make_aware(value, datetime_timezone.utc).astimezone(zone)


def _start_of(day, zone):
    naive = datetime.combine(day, time.min)
    return timezone.make_aware(naive, zone)


def _hour_label(hour: int) -> str:
    suffix = "am" if hour < 12 else "pm"
    hour12 = hour % 12 or 12
    return f"{hour12}{suffix}"


def _bounds(shop, days: int):
    zone = _shop_zone(shop)
    end_date = timezone.localdate(timezone=zone)
    start_date = end_date - timedelta(days=days - 1)
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=days - 1)
    return {
        "days": days,
        "zone": zone,
        "start_date": start_date,
        "prev_start_date": prev_start_date,
        "current_start": _start_of(start_date, zone),
        "current_end": _start_of(end_date + timedelta(days=1), zone),
        "prev_start": _start_of(prev_start_date, zone),
        "prev_end": _start_of(start_date, zone),
    }


def _sales(shop, start, end):
    return Sale.objects.filter(shop=shop, created_at__gte=start, created_at__lt=end)


def _items(shop, start, end):
    return SaleItem.objects.filter(
        sale__shop=shop,
        sale__created_at__gte=start,
        sale__created_at__lt=end,
    )


def _daily_amounts(queryset, amount_field: str, zone):
    totals = {}
    for created_at, amount in queryset.values_list("created_at", amount_field):
        local = _local_stamp(created_at, zone)
        if local is None:
            continue
        day = local.date()
        totals[day] = totals.get(day, Decimal("0")) + (amount or Decimal("0"))
    return {day: _money(total) for day, total in totals.items()}


def _comparison(current, previous):
    return {"current": current, "previous": previous}


def _sales_trend(shop, bounds):
    zone = bounds["zone"]
    current = _daily_amounts(_sales(shop, bounds["current_start"], bounds["current_end"]), "total", zone)
    previous = _daily_amounts(_sales(shop, bounds["prev_start"], bounds["prev_end"]), "total", zone)
    points = []
    for offset in range(bounds["days"]):
        day = bounds["start_date"] + timedelta(days=offset)
        prev_day = bounds["prev_start_date"] + timedelta(days=offset)
        points.append(
            {
                "label": f"{day.strftime('%b')} {day.day}",
                "current": current.get(day, 0),
                "previous": previous.get(prev_day, 0),
            }
        )
    return points


def _categories(shop, start, end):
    rows = (
        _items(shop, start, end)
        .values("product__category__name")
        .annotate(total=Coalesce(Sum("total"), ZERO))
        .order_by("-total")
    )
    amounts = [(row["product__category__name"] or "Uncategorized", _money(row["total"])) for row in rows]
    revenue = sum(amount for _, amount in amounts)
    return [
        {
            "category": name,
            "total": amount,
            "share": round(amount / revenue * 100, 1) if revenue else 0,
        }
        for name, amount in amounts
        if amount > 0
    ]


def _sales_by_hour(shop, start, end, zone):
    buckets = [Decimal("0")] * 24
    for created_at, total in _sales(shop, start, end).values_list("created_at", "total"):
        local = _local_stamp(created_at, zone)
        if local is None:
            continue
        buckets[local.hour] += total or Decimal("0")
    buckets = [_money(total) for total in buckets]
    active = [index for index, total in enumerate(buckets) if total]
    start_hour, end_hour = 8, 21
    if active:
        start_hour = min(start_hour, min(active))
        end_hour = max(end_hour, max(active))
    return [{"label": _hour_label(hour), "total": round(buckets[hour], 2)} for hour in range(start_hour, end_hour + 1)]


def _top_products(shop, start, end):
    rows = (
        _items(shop, start, end)
        .values("product__name")
        .annotate(revenue=Coalesce(Sum("total"), ZERO))
        .order_by("-revenue")[:8]
    )
    return [
        {"name": row["product__name"], "revenue": _money(row["revenue"])}
        for row in rows
        if _money(row["revenue"]) > 0
    ]


def _payment_methods(shop, start, end):
    rows = _sales(shop, start, end).values("payment_method").annotate(count=Count("id"))
    counts = {row["payment_method"]: row["count"] for row in rows}
    total = sum(counts.values())
    methods = []
    for code in PAYMENT_ORDER:
        count = counts.get(code, 0)
        if not count:
            continue
        methods.append(
            {
                "method": PAYMENT_LABELS.get(code, code),
                "count": count,
                "share": round(count / total * 100, 1) if total else 0,
            }
        )
    return methods


def _sales_by_cashier(shop, start, end):
    rows = (
        _sales(shop, start, end)
        .values("cashier__name")
        .annotate(total=Coalesce(Sum("total"), ZERO))
        .order_by("-total")[:8]
    )
    return [
        {"name": row["cashier__name"] or "Unknown", "total": _money(row["total"])}
        for row in rows
        if _money(row["total"]) > 0
    ]


def _discounts_and_refunds(shop, bounds):
    days = bounds["days"]
    weeks = max(2, round(days / 7))
    zone = bounds["zone"]
    discounts = _daily_amounts(_sales(shop, bounds["current_start"], bounds["current_end"]), "discount", zone)
    refunds = _daily_amounts(
        SalesReturn.objects.filter(
            shop=shop,
            created_at__gte=bounds["current_start"],
            created_at__lt=bounds["current_end"],
        ),
        "refund_amount",
        zone,
    )
    discount_buckets = [0.0] * weeks
    refund_buckets = [0.0] * weeks
    for offset in range(days):
        bucket = min(weeks - 1, (offset * weeks) // days)
        day = bounds["start_date"] + timedelta(days=offset)
        discount_buckets[bucket] += discounts.get(day, 0)
        refund_buckets[bucket] += refunds.get(day, 0)
    return [
        {
            "label": f"Wk {index + 1}",
            "discounts": round(discount_buckets[index], 2),
            "refunds": round(refund_buckets[index], 2),
        }
        for index in range(weeks)
    ]


def _low_stock(shop):
    products = (
        Product.objects.filter(shop=shop, status=True, stock_quantity__lte=F("reorder_level"))
        .select_related("category")
        .order_by("stock_quantity", "name")[:8]
    )
    rows = []
    for product in products:
        stock = float(product.stock_quantity)
        stock_value = int(stock) if stock == int(stock) else round(stock, 3)
        rows.append(
            {
                "id": product.id,
                "name": product.name,
                "category": product.category.name if product.category_id else "Uncategorized",
                "stock": stock_value,
                "reorder_level": product.reorder_level,
                "status": "out" if stock <= 0 else "low",
            }
        )
    return rows


def _recent_sales(shop):
    sales = Sale.objects.filter(shop=shop).select_related("cashier").order_by("-created_at")[:6]
    return [
        {
            "reference": sale.reference,
            "created_at": sale.created_at.isoformat(),
            "cashier": sale.cashier.name if sale.cashier_id else "Unknown",
            "payment_method": PAYMENT_LABELS.get(sale.payment_method, sale.payment_method),
            "total": _money(sale.total),
        }
        for sale in sales
    ]


def build_overview(shop, days: int) -> dict:
    bounds = _bounds(shop, days)
    zone = bounds["zone"]
    current = period_totals(shop, bounds["current_start"], bounds["current_end"])
    previous = period_totals(shop, bounds["prev_start"], bounds["prev_end"])
    return {
        "days": days,
        "kpis": {
            "total_sales": _comparison(current["revenue"], previous["revenue"]),
            "transactions": _comparison(current["transactions"], previous["transactions"]),
            "average_order_value": _comparison(current["average_order_value"], previous["average_order_value"]),
            "gross_profit": _comparison(current["gross_profit"], previous["gross_profit"]),
            "items_per_transaction": _comparison(
                current["items_per_transaction"], previous["items_per_transaction"]
            ),
            "refunds": _comparison(current["refunds"], previous["refunds"]),
        },
        "sales_trend": _sales_trend(shop, bounds),
        "categories": _categories(shop, bounds["current_start"], bounds["current_end"]),
        "sales_by_hour": _sales_by_hour(shop, bounds["current_start"], bounds["current_end"], zone),
        "top_products": _top_products(shop, bounds["current_start"], bounds["current_end"]),
        "payment_methods": _payment_methods(shop, bounds["current_start"], bounds["current_end"]),
        "sales_by_cashier": _sales_by_cashier(shop, bounds["current_start"], bounds["current_end"]),
        "discounts_and_refunds": _discounts_and_refunds(shop, bounds),
        "low_stock": _low_stock(shop),
        "recent_sales": _recent_sales(shop),
    }
