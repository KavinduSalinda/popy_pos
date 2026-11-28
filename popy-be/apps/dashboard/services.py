"""Aggregations for the dashboard overview."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product
from apps.sales.figures import (
    local_stamp,
    money_float,
    recognize_period,
    shop_zone,
    start_of_day,
    totals_from_activity,
)
from apps.sales.models import Sale

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
    return shop_zone(shop)


def _local_stamp(value, zone):
    return local_stamp(value, zone)


def _start_of(day, zone):
    return start_of_day(day, zone)


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


def _comparison(current, previous):
    return {"current": current, "previous": previous}


def _day(value, zone):
    local = _local_stamp(value, zone)
    return local.date() if local else None


def _add_day(totals, day, amount):
    if day is None:
        return
    totals[day] = totals.get(day, Decimal("0")) + amount


def _daily_net(activity, zone):
    totals = {}
    for sale in activity["sales"]:
        _add_day(totals, _day(sale["at"], zone), sale["money"])
    for ret in activity["returns"]:
        _add_day(totals, _day(ret["at"], zone), -ret["money"])
    return {day: _money(total) for day, total in totals.items()}


def _sales_trend(current, previous, bounds):
    zone = bounds["zone"]
    current_days = _daily_net(current, zone)
    previous_days = _daily_net(previous, zone)
    points = []
    for offset in range(bounds["days"]):
        day = bounds["start_date"] + timedelta(days=offset)
        prev_day = bounds["prev_start_date"] + timedelta(days=offset)
        points.append(
            {
                "label": f"{day.strftime('%b')} {day.day}",
                "current": current_days.get(day, 0),
                "previous": previous_days.get(prev_day, 0),
            }
        )
    return points


def _grouped_line_money(activity):
    totals = {}
    for sale in activity["sales"]:
        for line in sale["lines"]:
            key = (line["category"], line["name"], line["product_id"])
            totals[key] = totals.get(key, Decimal("0")) + line["revenue"]
    for ret in activity["returns"]:
        for line in ret["lines"]:
            key = (line["category"], line["name"], line["product_id"])
            totals[key] = totals.get(key, Decimal("0")) - line["money"]
    return totals


def _categories(activity):
    totals = {}
    for (category, _name, _product_id), amount in _grouped_line_money(activity).items():
        totals[category] = totals.get(category, Decimal("0")) + amount
    amounts = sorted(
        ((name, _money(total)) for name, total in totals.items() if total != 0),
        key=lambda row: row[1],
        reverse=True,
    )
    revenue = sum(amount for _, amount in amounts)
    return [
        {
            "category": name,
            "total": amount,
            "share": round(amount / revenue * 100, 1) if revenue else 0,
        }
        for name, amount in amounts
    ]


def _sales_by_hour(activity, zone):
    buckets = [Decimal("0")] * 24
    for sale in activity["sales"]:
        local = _local_stamp(sale["at"], zone)
        if local is not None:
            buckets[local.hour] += sale["money"]
    for ret in activity["returns"]:
        local = _local_stamp(ret["at"], zone)
        if local is not None:
            buckets[local.hour] -= ret["money"]
    shown = [_money(total) for total in buckets]
    active = [index for index, total in enumerate(shown) if total]
    start_hour, end_hour = 8, 21
    if active:
        start_hour = min(start_hour, min(active))
        end_hour = max(end_hour, max(active))
    return [{"label": _hour_label(hour), "total": round(shown[hour], 2)} for hour in range(start_hour, end_hour + 1)]


def _top_products(activity):
    totals = {}
    for (_category, name, _product_id), amount in _grouped_line_money(activity).items():
        totals[name] = totals.get(name, Decimal("0")) + amount
    ranked = sorted(totals.items(), key=lambda row: row[1], reverse=True)
    return [{"name": name, "revenue": _money(amount)} for name, amount in ranked if amount != 0][:8]


def _payment_methods(activity):
    counts = {}
    for sale in activity["sales"]:
        if not sale["counts"]:
            continue
        counts[sale["payment_method"]] = counts.get(sale["payment_method"], 0) + 1
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


def _sales_by_cashier(activity):
    totals = {}
    for sale in activity["sales"]:
        totals[sale["cashier"]] = totals.get(sale["cashier"], Decimal("0")) + sale["money"]
    for ret in activity["returns"]:
        totals[ret["cashier"]] = totals.get(ret["cashier"], Decimal("0")) - ret["money"]
    ranked = sorted(totals.items(), key=lambda row: row[1], reverse=True)
    return [{"name": name, "total": _money(amount)} for name, amount in ranked if amount != 0][:8]


def _discounts_and_refunds(activity, bounds):
    days = bounds["days"]
    weeks = max(2, round(days / 7))
    zone = bounds["zone"]
    discounts = {}
    refunds = {}
    for sale in activity["sales"]:
        _add_day(discounts, _day(sale["at"], zone), sale["discount"])
    for ret in activity["returns"]:
        _add_day(refunds, _day(ret["at"], zone), ret["money"])
    discount_days = {day: _money(total) for day, total in discounts.items()}
    refund_days = {day: _money(total) for day, total in refunds.items()}
    discount_buckets = [0.0] * weeks
    refund_buckets = [0.0] * weeks
    for offset in range(days):
        bucket = min(weeks - 1, (offset * weeks) // days)
        day = bounds["start_date"] + timedelta(days=offset)
        discount_buckets[bucket] += discount_days.get(day, 0)
        refund_buckets[bucket] += refund_days.get(day, 0)
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
    current_activity = recognize_period(shop, bounds["current_start"], bounds["current_end"])
    previous_activity = recognize_period(shop, bounds["prev_start"], bounds["prev_end"])
    current = totals_from_activity(current_activity)
    previous = totals_from_activity(previous_activity)
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
        "sales_trend": _sales_trend(current_activity, previous_activity, bounds),
        "categories": _categories(current_activity),
        "sales_by_hour": _sales_by_hour(current_activity, zone),
        "top_products": _top_products(current_activity),
        "payment_methods": _payment_methods(current_activity),
        "sales_by_cashier": _sales_by_cashier(current_activity),
        "discounts_and_refunds": _discounts_and_refunds(current_activity, bounds),
        "low_stock": _low_stock(shop),
        "recent_sales": _recent_sales(shop),
    }
