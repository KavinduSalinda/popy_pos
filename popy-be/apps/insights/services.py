"""Product requirement estimates for the next 7, 30, and 90 days."""

from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import Product
from apps.dashboard.services import build_overview
from apps.sales.models import SaleItem

LOOKBACK_DAYS = 30
HORIZONS = (7, 30, 90)


def _whole(value: Decimal) -> int:
    if value <= 0:
        return 0
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _number(value: Decimal):
    if value == value.to_integral():
        return int(value)
    return float(value)


def build_requirements(shop) -> dict:
    """Estimate units to buy from the last 30 days of sales for this shop only."""
    start = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    sold_rows = (
        SaleItem.objects.filter(
            sale__shop=shop,
            sale__created_at__gte=start,
            product__shop=shop,
            product__status=True,
        )
        .values("product_id")
        .annotate(units=Sum("quantity"))
    )
    sold_by_product = {row["product_id"]: row["units"] or Decimal("0") for row in sold_rows}

    rows = []
    for product in Product.objects.filter(shop=shop, status=True).order_by("name"):
        sold = sold_by_product.get(product.id, Decimal("0"))
        per_day = sold / Decimal(LOOKBACK_DAYS)
        row = {
            "product": product.name,
            "sku": product.sku,
            "stock": _number(product.stock_quantity),
            "sold_last30": _number(sold),
            "per_day": round(float(per_day), 3),
        }
        for horizon in HORIZONS:
            need = _whole((sold * Decimal(horizon)) / Decimal(LOOKBACK_DAYS))
            buy = _whole(Decimal(need) - product.stock_quantity)
            row[f"need{horizon}"] = need
            row[f"buy{horizon}"] = buy
        rows.append(row)

    rows.sort(key=lambda item: (-item["buy30"], -item["buy90"], item["product"].lower()))
    summary = {
        "buy7": sum(item["buy7"] for item in rows),
        "buy30": sum(item["buy30"] for item in rows),
        "buy90": sum(item["buy90"] for item in rows),
    }
    return {"lookback_days": LOOKBACK_DAYS, "rows": rows, "summary": summary}


def model_facts(shop) -> dict:
    """Short snapshot for Groq. No customers, cashiers, or sale references."""
    report = build_requirements(shop)
    overview = build_overview(shop, LOOKBACK_DAYS)
    kpis = overview["kpis"]
    products = [
        {
            "product": row["product"],
            "sku": row["sku"],
            "stock": row["stock"],
            "per_day": row["per_day"],
            "need7": row["need7"],
            "need30": row["need30"],
            "need90": row["need90"],
            "buy7": row["buy7"],
            "buy30": row["buy30"],
            "buy90": row["buy90"],
        }
        for row in report["rows"]
        if row["buy7"] or row["buy30"] or row["buy90"]
    ][:15]
    return {
        "based_on_days": LOOKBACK_DAYS,
        "units_to_buy": report["summary"],
        "products_to_buy": products,
        "recent_trading": {
            "revenue": kpis["total_sales"],
            "transactions": kpis["transactions"],
            "gross_profit": kpis["gross_profit"],
        },
    }


def prediction_fallback(facts: dict) -> str:
    totals = facts["units_to_buy"]
    return (
        "This is an estimate from the last 30 days of sales. "
        f"Buy about {totals['buy7']} units to cover 7 days, "
        f"{totals['buy30']} units to cover 30 days, and "
        f"{totals['buy90']} units to cover 90 days."
    )
