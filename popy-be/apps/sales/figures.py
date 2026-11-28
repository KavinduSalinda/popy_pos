"""Sale line profit and return application shared by the dashboard and returns."""

from decimal import Decimal, ROUND_HALF_UP

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
    def __init__(self, money, profit, units, taken):
        self.money = money
        self.profit = profit
        self.units = units
        self.taken = taken


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
        net = gross - share
        lines.append(
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "remaining": item.quantity,
                "net": net,
                "profit": net - (_dec(cost) * item.quantity),
            }
        )
    profit = sum((line["profit"] for line in lines), Decimal("0"))
    units = sum((line["quantity"] for line in lines), Decimal("0"))
    collected = max(_dec(sale.total), Decimal("0"))
    return SaleState(sale, lines, collected, profit, units)


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


def _clamp(state: SaleState, profit_reversed: Decimal, units_reversed: Decimal):
    if units_reversed < 0:
        units_reversed = Decimal("0")
    units_reversed = min(units_reversed, state.units_left)
    if state.profit_left >= 0:
        profit_reversed = min(max(profit_reversed, Decimal("0")), state.profit_left)
    else:
        profit_reversed = max(min(profit_reversed, Decimal("0")), state.profit_left)
    return profit_reversed, units_reversed


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

    def add_taken(product_id: int, qty: Decimal):
        if qty > 0:
            taken_map[product_id] = taken_map.get(product_id, Decimal("0")) + qty

    if not items:
        if state.collected > 0:
            fraction = applied / state.collected
            units_reversed = state.units * fraction
            profit_reversed = state.profit * fraction
        elif not state.zero_collected_done:
            units_reversed = sum((line["remaining"] for line in state.lines), Decimal("0"))
            profit_reversed = state.profit_left
            state.zero_collected_done = True
        for line in state.lines:
            if line["remaining"] > 0:
                add_taken(line["product_id"], line["remaining"])
            line["remaining"] = Decimal("0")
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
                take = min(left, line["remaining"])
                if take <= 0:
                    continue
                if line["quantity"] > 0:
                    profit_reversed += line["profit"] * (take / line["quantity"])
                units_reversed += take
                line["remaining"] -= take
                left -= take
                add_taken(product_id, take)

    profit_reversed, units_reversed = _clamp(state, profit_reversed, units_reversed)
    state.profit_left -= profit_reversed
    state.units_left -= units_reversed
    taken = [{"product_id": product_id, "quantity": qty} for product_id, qty in taken_map.items()]
    return AppliedReturn(applied, profit_reversed, units_reversed, taken)


def replay_returns(state: SaleState, returns) -> None:
    ordered = sorted(returns, key=lambda ret: (ret.created_at, ret.id))
    for ret in ordered:
        apply_return(state, items=ret.items, refund_amount=ret.refund_amount)


def state_after_returns(sale) -> SaleState:
    state = build_sale_state(sale)
    replay_returns(state, sale.returns.all())
    return state


def period_totals(shop, start, end) -> dict:
    from apps.returns.models import SalesReturn
    from apps.sales.models import Sale

    sales = list(
        Sale.objects.filter(shop=shop, created_at__gte=start, created_at__lt=end).prefetch_related(
            "items__product"
        )
    )
    window_returns = list(
        SalesReturn.objects.filter(shop=shop, created_at__gte=start, created_at__lt=end)
        .select_related("sale")
        .order_by("created_at", "id")
    )
    extra_ids = {ret.sale_id for ret in window_returns} - {sale.id for sale in sales}
    extras = []
    if extra_ids:
        extras = list(Sale.objects.filter(pk__in=extra_ids).prefetch_related("items__product"))
    states = {sale.id: build_sale_state(sale) for sale in [*sales, *extras]}
    if states:
        prior = SalesReturn.objects.filter(sale_id__in=states.keys(), created_at__lt=start).order_by(
            "created_at", "id"
        )
        for ret in prior:
            state = states.get(ret.sale_id)
            if state is not None:
                apply_return(state, items=ret.items, refund_amount=ret.refund_amount)
    collected = Decimal("0")
    profit = Decimal("0")
    units = Decimal("0")
    for sale in sales:
        state = states[sale.id]
        collected += state.collected
        profit += state.profit
        units += state.units
    refunds = Decimal("0")
    for ret in window_returns:
        state = states.get(ret.sale_id)
        if state is None:
            continue
        applied = apply_return(state, items=ret.items, refund_amount=ret.refund_amount)
        collected -= applied.money
        profit -= applied.profit
        units -= applied.units
        refunds += applied.money
    transactions = len(sales)
    return {
        "revenue": money_float(collected),
        "transactions": transactions,
        "average_order_value": money_float(collected / transactions) if transactions else 0.0,
        "gross_profit": money_float(profit),
        "items_per_transaction": tenth_float(units / transactions) if transactions else 0.0,
        "refunds": money_float(refunds),
    }
