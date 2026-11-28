"""Sale line profit and return application shared by the dashboard and returns."""

from datetime import datetime, time, timezone as datetime_timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.utils import timezone

CENT = Decimal("0.01")
TENTH = Decimal("0.1")


class ReturnQuantityError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _dec(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value) -> Decimal:
    return _dec(value).quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_tenth(value) -> Decimal:
    return _dec(value).quantize(TENTH, rounding=ROUND_HALF_UP)


def money_float(value) -> float:
    return float(quantize_money(value))


def tenth_float(value) -> float:
    return float(quantize_tenth(value))


def shop_zone(shop):
    name = (getattr(shop, "timezone", None) or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def local_stamp(value, zone):
    if value is None:
        return None
    if timezone.is_aware(value):
        return value.astimezone(zone)
    return timezone.make_aware(value, datetime_timezone.utc).astimezone(zone)


def start_of_day(day, zone):
    return timezone.make_aware(datetime.combine(day, time.min), zone)


class SaleState:
    def __init__(self, sale, lines, collected, profit, units):
        self.sale = sale
        self.lines = lines
        self.collected = collected
        self.remaining_collected = collected
        self.profit = profit
        self.profit_left = profit
        self.units = units
        self.units_left = units
        self.zero_collected_done = False


class AppliedReturn:
    def __init__(self, money, profit, units, taken, lines):
        self.money = money
        self.profit = profit
        self.units = units
        self.taken = taken
        self.lines = lines


def build_sale_state(sale) -> SaleState:
    items = list(sale.items.all())
    items.sort(key=lambda item: item.id or 0)
    merchandise = sum((item.unit_price * item.quantity for item in items), Decimal("0"))
    raw_discount = _dec(sale.discount)
    discount = min(max(raw_discount, Decimal("0")), merchandise) if merchandise > 0 else Decimal("0")
    allocated = Decimal("0")
    lines = []
    last = len(items) - 1
    for index, item in enumerate(items):
        gross = item.unit_price * item.quantity
        if index == last:
            share = discount - allocated
        elif merchandise > 0:
            share = (discount * gross / merchandise).quantize(CENT, rounding=ROUND_HALF_UP)
            allocated += share
        else:
            share = Decimal("0")
        cost = item.cost_price if item.cost_price is not None else item.product.cost_price
        product = item.product
        category = "Uncategorized"
        if getattr(product, "category_id", None):
            category = product.category.name or "Uncategorized"
        net = gross - share
        lines.append(
            {
                "product_id": item.product_id,
                "name": product.name,
                "category": category,
                "quantity": item.quantity,
                "remaining": item.quantity,
                "net": net,
                "profit": net - (_dec(cost) * item.quantity),
                "revenue": net,
            }
        )
    profit = sum((line["profit"] for line in lines), Decimal("0"))
    units = sum((line["quantity"] for line in lines), Decimal("0"))
    collected = max(_dec(sale.total), Decimal("0"))
    _spread_revenue(lines, collected)
    return SaleState(sale, lines, collected, profit, units)


def _spread_revenue(lines, collected: Decimal) -> None:
    """Make line revenue add up to the collected sale total, tax included."""
    if not lines:
        return
    net_sum = sum((line["net"] for line in lines), Decimal("0"))
    extra = collected - net_sum
    positive = [(index, line["net"]) for index, line in enumerate(lines) if line["net"] > 0]
    if extra == 0 or not positive:
        if extra != 0:
            lines[-1]["revenue"] = lines[-1]["net"] + extra
        return
    base = sum((net for _, net in positive), Decimal("0"))
    allocated = Decimal("0")
    last_index = positive[-1][0]
    for index, net in positive[:-1]:
        share = (extra * net / base).quantize(CENT, rounding=ROUND_HALF_UP)
        lines[index]["revenue"] = lines[index]["net"] + share
        allocated += share
    lines[last_index]["revenue"] = lines[last_index]["net"] + (extra - allocated)


def product_remaining(state: SaleState, product_id: int) -> Decimal:
    return sum(
        (line["remaining"] for line in state.lines if line["product_id"] == product_id),
        Decimal("0"),
    )


def units_remaining(state: SaleState) -> Decimal:
    return sum((line["remaining"] for line in state.lines), Decimal("0"))


def item_qty_map(items) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = {}
    if not items:
        return totals
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("productId", item.get("product_id"))
        if raw_id in (None, ""):
            continue
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        qty = _dec(item.get("quantity"))
        if qty <= 0:
            continue
        totals[product_id] = totals.get(product_id, Decimal("0")) + qty
    return totals


def _portion(line, take: Decimal) -> tuple[Decimal, Decimal]:
    if take <= 0 or line["quantity"] <= 0:
        return Decimal("0"), Decimal("0")
    ratio = take / line["quantity"]
    return line["profit"] * ratio, line["revenue"] * ratio


def suggested_quantity(remaining: Decimal) -> Decimal:
    if remaining >= 1:
        return Decimal("1")
    if remaining > 0:
        return remaining
    return Decimal("0")


def quote_product(state: SaleState, product_id: int, quantity: Decimal) -> Decimal:
    left = quantity
    refund = Decimal("0")
    for line in state.lines:
        if line["product_id"] != product_id or left <= 0:
            continue
        take = min(left, line["remaining"])
        if line["quantity"] > 0 and take > 0:
            refund += line["net"] * (take / line["quantity"])
        left -= take
    return min(quantize_money(refund), state.remaining_collected)


def apply_return(state: SaleState, *, items, refund_amount, strict: bool = False) -> AppliedReturn:
    refund = max(_dec(refund_amount), Decimal("0"))
    applied = min(refund, state.remaining_collected)
    state.remaining_collected -= applied

    units_reversed = Decimal("0")
    profit_reversed = Decimal("0")
    taken_map: dict[int, Decimal] = {}
    taken_lines: list[dict] = []

    def take(line, qty: Decimal):
        nonlocal units_reversed, profit_reversed
        take_qty = min(qty, line["remaining"])
        if take_qty <= 0:
            return
        profit_part, weight = _portion(line, take_qty)
        profit_reversed += profit_part
        units_reversed += take_qty
        line["remaining"] -= take_qty
        taken_map[line["product_id"]] = taken_map.get(line["product_id"], Decimal("0")) + take_qty
        taken_lines.append(
            {
                "product_id": line["product_id"],
                "name": line["name"],
                "category": line["category"],
                "quantity": take_qty,
                "profit": profit_part,
                "weight": weight,
            }
        )

    if not items:
        for line in state.lines:
            take(line, line["remaining"])
        if state.collected <= 0:
            state.zero_collected_done = True
    else:
        requested = item_qty_map(items)
        if strict:
            for product_id, qty in requested.items():
                if qty > product_remaining(state, product_id):
                    raise ReturnQuantityError("Quantity is higher than what is left to return.")
            if not requested:
                raise ReturnQuantityError("Quantity is higher than what is left to return.")
        for product_id, qty in requested.items():
            left = qty
            for line in state.lines:
                if line["product_id"] != product_id or left <= 0:
                    continue
                before = line["remaining"]
                take(line, left)
                left -= before - line["remaining"]

    state.profit_left -= profit_reversed
    state.units_left -= units_reversed
    taken = [{"product_id": product_id, "quantity": qty} for product_id, qty in taken_map.items()]
    return AppliedReturn(applied, profit_reversed, units_reversed, taken, taken_lines)


def replay_returns(state: SaleState, returns) -> None:
    ordered = sorted(returns, key=lambda ret: (ret.created_at, ret.id))
    for ret in ordered:
        apply_return(state, items=ret.items, refund_amount=ret.refund_amount)


def state_after_returns(sale) -> SaleState:
    state = build_sale_state(sale)
    replay_returns(state, sale.returns.all())
    return state


def _split_money(amount: Decimal, parts: list[dict]) -> None:
    if not parts:
        return
    if amount == 0:
        for part in parts:
            part["money"] = Decimal("0")
        return
    weight = sum((part["weight"] for part in parts), Decimal("0"))
    allocated = Decimal("0")
    if weight <= 0:
        share = (amount / len(parts)).quantize(CENT, rounding=ROUND_HALF_UP)
        for part in parts[:-1]:
            part["money"] = share
            allocated += share
    else:
        for part in parts[:-1]:
            share = (amount * part["weight"] / weight).quantize(CENT, rounding=ROUND_HALF_UP)
            part["money"] = share
            allocated += share
    parts[-1]["money"] = amount - allocated


def _counts_as_transaction(state: SaleState) -> bool:
    if state.collected > 0:
        return state.remaining_collected > 0
    return state.units_left > 0


def _sale_event(sale, state: SaleState) -> dict:
    return {
        "at": sale.created_at,
        "money": state.collected,
        "profit": state.profit,
        "units": state.units,
        "discount": _dec(sale.discount),
        "payment_method": sale.payment_method,
        "cashier": sale.cashier.name if sale.cashier_id else "Unknown",
        "customer_id": sale.customer_id,
        "lines": [
            {
                "product_id": line["product_id"],
                "name": line["name"],
                "category": line["category"],
                "revenue": line["revenue"],
                "profit": line["profit"],
                "units": line["quantity"],
            }
            for line in state.lines
        ],
        "counts": False,
    }


def _return_event(ret, sale, applied: AppliedReturn) -> dict:
    lines = [dict(line) for line in applied.lines]
    _split_money(applied.money, lines)
    for line in lines:
        line["units"] = line["quantity"]
    return {
        "at": ret.created_at,
        "money": applied.money,
        "profit": applied.profit,
        "units": applied.units,
        "payment_method": sale.payment_method,
        "cashier": sale.cashier.name if sale.cashier_id else "Unknown",
        "customer_id": sale.customer_id,
        "lines": lines,
    }


def _window_filter(queryset, start, end, inclusive_end: bool):
    if start is not None:
        queryset = queryset.filter(created_at__gte=start)
    if end is not None:
        lookup = "created_at__lte" if inclusive_end else "created_at__lt"
        queryset = queryset.filter(**{lookup: end})
    return queryset


def recognize_period(shop, start, end, *, inclusive_end: bool = False) -> dict:
    """Sales and returns recognized between start and end.

    A sale adds its collected total. A return subtracts cash, profit, and units
    on the return's timestamp. Line revenue includes tax and already excludes
    the sale discount. Profit uses the cost saved on the sale line.
    """
    from apps.returns.models import SalesReturn
    from apps.sales.models import Sale

    prefetched = (
        "items__product__category",
    )
    sales = list(
        _window_filter(Sale.objects.filter(shop=shop), start, end, inclusive_end)
        .select_related("cashier", "customer")
        .prefetch_related(*prefetched)
    )
    window_returns = list(
        _window_filter(SalesReturn.objects.filter(shop=shop), start, end, inclusive_end)
        .select_related("sale__cashier", "sale__customer")
        .order_by("created_at", "id")
    )
    extra_ids = {ret.sale_id for ret in window_returns} - {sale.id for sale in sales}
    extras = []
    if extra_ids:
        extras = list(
            Sale.objects.filter(pk__in=extra_ids)
            .select_related("cashier", "customer")
            .prefetch_related(*prefetched)
        )
    states = {}
    sale_events = []
    in_window = {sale.id for sale in sales}
    for sale in [*sales, *extras]:
        state = build_sale_state(sale)
        states[sale.id] = state
        if sale.id in in_window:
            sale_events.append(_sale_event(sale, state))
    if start is not None and states:
        prior = SalesReturn.objects.filter(sale_id__in=states.keys(), created_at__lt=start).order_by(
            "created_at", "id"
        )
        for ret in prior:
            state = states.get(ret.sale_id)
            if state is not None:
                apply_return(state, items=ret.items, refund_amount=ret.refund_amount)
    return_events = []
    for ret in window_returns:
        state = states.get(ret.sale_id)
        if state is None:
            continue
        applied = apply_return(state, items=ret.items, refund_amount=ret.refund_amount)
        return_events.append(_return_event(ret, state.sale, applied))
    for sale, event in zip(sales, sale_events):
        event["counts"] = _counts_as_transaction(states[sale.id])
    return {"sales": sale_events, "returns": return_events}


def totals_from_activity(activity: dict) -> dict:
    sales = activity["sales"]
    returns = activity["returns"]
    revenue = sum((row["money"] for row in sales), Decimal("0")) - sum(
        (row["money"] for row in returns), Decimal("0")
    )
    profit = sum((row["profit"] for row in sales), Decimal("0")) - sum(
        (row["profit"] for row in returns), Decimal("0")
    )
    units = sum((row["units"] for row in sales), Decimal("0")) - sum(
        (row["units"] for row in returns), Decimal("0")
    )
    refunds = sum((row["money"] for row in returns), Decimal("0"))
    transactions = sum(1 for row in sales if row["counts"])
    return {
        "revenue": money_float(revenue),
        "transactions": transactions,
        "average_order_value": money_float(revenue / transactions) if transactions else 0.0,
        "gross_profit": money_float(profit),
        "items_per_transaction": tenth_float(units / transactions) if transactions else 0.0,
        "refunds": money_float(refunds),
    }


def period_totals(shop, start, end, *, inclusive_end: bool = False) -> dict:
    return totals_from_activity(recognize_period(shop, start, end, inclusive_end=inclusive_end))
