"""Aggregations for the dashboard overview."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncHour
from django.utils import timezone

from apps.catalog.models import Product
from apps.returns.models import SalesReturn
from apps.sales.models import Sale, SaleItem

MONEY = DecimalField(max_digits=16, decimal_places=2)
ZERO = Value(Decimal("0"), output_field=MONEY)
QTY = DecimalField(max_digits=16, decimal_places=3)
ZERO_QTY = Value(Decimal("0"), output_field=QTY)

PAYMENT_LABELS = {
    "CASH": "Cash",
    "CARD": "Card",
    "MOBILE": "Mobile",
    "CREDIT": "Credit",
}
PAYMENT_ORDER = ("CASH", "CARD", "MOBILE", "CREDIT")


def _money(value) -> float:
    return round(float(value or 0), 2)


def _as_date(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _start_of(day):
    naive = datetime.combine(day, time.min)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _hour_label(hour: int) -> str:
    suffix = "am" if hour < 12 else "pm"
    hour12 = hour % 12 or 12
    return f"{hour12}{suffix}"


def _bounds(days: int):
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=days - 1)
    return {
        "days": days,
        "start_date": start_date,
        "prev_start_date": prev_start_date,
        "current_start": _start_of(start_date),
        "current_end": _start_of(end_date + timedelta(days=1)),
        "prev_start": _start_of(prev_start_date),
        "prev_end": _start_of(start_date),
    }


def _sales(shop, start, end):
    return Sale.objects.filter(shop=shop, created_at__gte=start, created_at__lt=end)


def _items(shop, start, end):
    return SaleItem.objects.filter(
        sale__shop=shop,
        sale__created_at__gte=start,
        sale__created_at__lt=end,
    )


def _daily_amounts(queryset, amount_field: str):
    rows = (
        queryset.annotate(day=TruncDay("created_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(total=Coalesce(Sum(amount_field), ZERO))
    )
    return {_as_date(row["day"]): _money(row["total"]) for row in rows if row["day"] is not None}


def _period_stats(shop, start, end):
    sale_agg = _sales(shop, start, end).aggregate(
        revenue=Coalesce(Sum("total"), ZERO),
        transactions=Count("id"),
        discounts=Coalesce(Sum("discount"), ZERO),
    )
    profit_expr = ExpressionWrapper(
        (F("unit_price") - F("product__cost_price")) * F("quantity"),
        output_field=MONEY,
    )
    item_agg = _items(shop, start, end).aggregate(
        units=Coalesce(Sum("quantity"), ZERO_QTY),
        profit=Coalesce(Sum(profit_expr), ZERO),
    )
    refunds = SalesReturn.objects.filter(shop=shop, created_at__gte=start, created_at__lt=end).aggregate(
        total=Coalesce(Sum("refund_amount"), ZERO)
    )
    transactions = sale_agg["transactions"] or 0
    revenue = sale_agg["revenue"] or Decimal("0")
    quantity = item_agg["units"] or Decimal("0")
    return {
        "revenue": _money(revenue),
        "transactions": transactions,
        "average_order_value": _money(revenue / transactions) if transactions else 0,
        "gross_profit": _money(item_agg["profit"]),
        "items_per_transaction": round(float(quantity) / transactions, 1) if transactions else 0,
        "refunds": _money(refunds["total"]),
        "discounts": _money(sale_agg["discounts"]),
    }


def _comparison(current, previous):
    return {"current": current, "previous": previous}


def _sales_trend(shop, bounds):
    current = _daily_amounts(_sales(shop, bounds["current_start"], bounds["current_end"]), "total")
    previous = _daily_amounts(_sales(shop, bounds["prev_start"], bounds["prev_end"]), "total")
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


def _sales_by_hour(shop, start, end):
    rows = (
        _sales(shop, start, end)
        .annotate(bucket=TruncHour("created_at", tzinfo=timezone.get_current_timezone()))
        .values("bucket")
        .annotate(total=Coalesce(Sum("total"), ZERO))
    )
    buckets = [0.0] * 24
    for row in rows:
        bucket = row["bucket"]
        if bucket is None:
            continue
        hour = timezone.localtime(bucket).hour if timezone.is_aware(bucket) else bucket.hour
        buckets[hour] += _money(row["total"])
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
    discounts = _daily_amounts(_sales(shop, bounds["current_start"], bounds["current_end"]), "discount")
    refunds = _daily_amounts(
        SalesReturn.objects.filter(
            shop=shop,
            created_at__gte=bounds["current_start"],
            created_at__lt=bounds["current_end"],
        ),
        "refund_amount",
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
    bounds = _bounds(days)
    current = _period_stats(shop, bounds["current_start"], bounds["current_end"])
    previous = _period_stats(shop, bounds["prev_start"], bounds["prev_end"])
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
        "sales_by_hour": _sales_by_hour(shop, bounds["current_start"], bounds["current_end"]),
        "top_products": _top_products(shop, bounds["current_start"], bounds["current_end"]),
        "payment_methods": _payment_methods(shop, bounds["current_start"], bounds["current_end"]),
        "sales_by_cashier": _sales_by_cashier(shop, bounds["current_start"], bounds["current_end"]),
        "discounts_and_refunds": _discounts_and_refunds(shop, bounds),
        "low_stock": _low_stock(shop),
        "recent_sales": _recent_sales(shop),
    }
