"""Resolve a sales return from a bill, barcode, or SKU."""

from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product
from apps.core.choices import StockTransactionType
from apps.core.services import adjust_stock
from apps.core.utils import generate_reference
from apps.purchasing.models import Purchase
from apps.returns.models import PurchaseReturn, SalesReturn
from apps.sales.figures import (
    ReturnQuantityError,
    apply_return,
    product_remaining,
    quantize_money,
    quote_product,
    state_after_returns,
    suggested_quantity,
    units_remaining,
)
from apps.sales.models import Sale


class ReturnLookupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _resolve_sale(shop, code: str):
    value = code.strip()
    if not value:
        return None
    queryset = Sale.objects.filter(shop=shop)
    if value.isdigit():
        sale = queryset.filter(pk=int(value)).first()
        if sale is not None:
            return sale
    return queryset.filter(reference__iexact=value).first()


def _resolve_product(shop, code: str):
    product = Product.objects.filter(shop=shop, sku__iexact=code).first()
    if product is not None:
        return product
    return Product.objects.filter(shop=shop, barcode__iexact=code).first()


def _sale_ids_for_product(shop, product_id: int) -> list[int]:
    seen = set()
    ordered = []
    rows = (
        Sale.objects.filter(shop=shop, items__product_id=product_id)
        .order_by("-created_at", "-id")
        .values_list("id", flat=True)
    )
    for sale_id in rows:
        if sale_id not in seen:
            seen.add(sale_id)
            ordered.append(sale_id)
    return ordered


def _lock_sale(sale_id: int) -> Sale:
    return (
        Sale.objects.select_for_update()
        .prefetch_related("items__product", "returns")
        .get(pk=sale_id)
    )


def _load_sale(sale_id: int) -> Sale:
    return Sale.objects.prefetch_related("items__product", "returns").get(pk=sale_id)


def _number(value: Decimal):
    quantized = value.quantize(Decimal("0.001"))
    if quantized == quantized.to_integral():
        return int(quantized)
    return float(quantized)


def _lookup_payload(kind: str, sale: Sale, state, product=None, quantity=None) -> dict:
    left = units_remaining(state) if product is None else product_remaining(state, product.id)
    if product is None:
        suggested_qty = left
        suggested_refund = state.remaining_collected
    else:
        suggested_qty = quantity if quantity is not None else suggested_quantity(left)
        suggested_refund = quote_product(state, product.id, suggested_qty)
    payload = {
        "match": kind,
        "sale_id": sale.id,
        "sale_reference": sale.reference,
        "quantity_left": _number(left),
        "suggested_quantity": _number(suggested_qty),
        "suggested_refund": float(quantize_money(suggested_refund)),
        "refund_left": float(quantize_money(state.remaining_collected)),
    }
    if product is not None:
        payload.update(
            {
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
            }
        )
    return payload


def lookup_code(shop, code: str) -> dict:
    value = (code or "").strip()
    if not value:
        raise ReturnLookupError("Barcode, SKU, or sale reference is required.", 400)
    sale = _resolve_sale(shop, value)
    if sale is not None:
        sale = _load_sale(sale.id)
        return _lookup_payload("sale", sale, state_after_returns(sale))
    product = _resolve_product(shop, value)
    if product is None:
        raise ReturnLookupError(f'No sale, barcode, or SKU found for "{value}".', 404)
    for sale_id in _sale_ids_for_product(shop, product.id):
        sale = _load_sale(sale_id)
        state = state_after_returns(sale)
        if product_remaining(state, product.id) > 0:
            return _lookup_payload("product", sale, state, product)
    raise ReturnLookupError("No returnable sale for this item.", 404)


def _restock(shop, taken, reference: str):
    for row in taken:
        product = Product.objects.select_for_update().get(pk=row["product_id"], shop=shop)
        adjust_stock(
            product,
            row["quantity"],
            StockTransactionType.RETURN,
            note=f"Sales return {reference}",
            reference_type="SalesReturn",
        )


def _stored_items(items) -> list[dict]:
    stored = []
    for product_id, qty in items.items():
        stored.append({"productId": product_id, "quantity": format(qty, "f")})
    return stored


@transaction.atomic
def create_sales_return(
    shop,
    *,
    code: str = "",
    sale_id: str = "",
    reason: str,
    refund_amount,
    items=None,
    quantity=None,
) -> SalesReturn:
    from apps.sales.figures import item_qty_map

    lookup = (code or "").strip() or str(sale_id or "").strip()
    if not lookup:
        raise ReturnLookupError("Enter a bill, barcode, or SKU.", 400)

    sale = _resolve_sale(shop, lookup)
    reference = generate_reference("SR", SalesReturn, shop=shop)
    if sale is not None:
        locked = _lock_sale(sale.id)
        state = state_after_returns(locked)
        item_list = items or []
        if item_list:
            try:
                applied = apply_return(
                    state,
                    items=item_list,
                    refund_amount=refund_amount,
                    strict=True,
                )
            except ReturnQuantityError as exc:
                raise ReturnLookupError(exc.message, 400) from exc
            stored = _stored_items(item_qty_map(item_list))
        else:
            if units_remaining(state) <= 0:
                raise ReturnLookupError("Nothing left to return on this sale.", 400)
            applied = apply_return(state, items=[], refund_amount=refund_amount)
            stored = []
        _restock(shop, applied.taken, reference)
        return SalesReturn.objects.create(
            shop=shop,
            reference=reference,
            sale=locked,
            reason=reason,
            refund_amount=quantize_money(applied.money),
            items=stored,
        )

    product = _resolve_product(shop, lookup)
    if product is None:
        raise ReturnLookupError(f'No sale, barcode, or SKU found for "{lookup}".', 404)

    requested = None if quantity is None else Decimal(str(quantity))
    if requested is not None and requested <= 0:
        raise ReturnLookupError("Enter a quantity.", 400)

    for sale_id_value in _sale_ids_for_product(shop, product.id):
        locked = _lock_sale(sale_id_value)
        state = state_after_returns(locked)
        left = product_remaining(state, product.id)
        if left <= 0:
            continue
        use_qty = suggested_quantity(left) if requested is None else requested
        if use_qty > left:
            raise ReturnLookupError("Quantity is higher than what is left to return.", 400)
        item_list = [{"productId": product.id, "quantity": format(use_qty, "f")}]
        applied = apply_return(state, items=item_list, refund_amount=refund_amount, strict=True)
        _restock(shop, applied.taken, reference)
        return SalesReturn.objects.create(
            shop=shop,
            reference=reference,
            sale=locked,
            reason=reason,
            refund_amount=quantize_money(applied.money),
            items=item_list,
        )
    raise ReturnLookupError("No returnable sale for this item.", 404)


def _purchase_lines(purchase: Purchase, items):
    lines = list(purchase.items.select_related("product"))
    by_product = {}
    for line in lines:
        by_product.setdefault(line.product_id, line)
    if not items:
        chosen = [(line.product_id, Decimal(line.quantity), line.cost_price) for line in lines]
    else:
        chosen = []
        for item in items:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("productId", item.get("product_id"))
            try:
                product_id = int(raw_id)
            except (TypeError, ValueError):
                raise ReturnLookupError("That product is not on this purchase.", 400) from None
            line = by_product.get(product_id)
            if line is None:
                raise ReturnLookupError("That product is not on this purchase.", 400)
            quantity = Decimal(str(item.get("quantity") or 0))
            if quantity <= 0:
                raise ReturnLookupError("Enter a quantity.", 400)
            chosen.append((product_id, quantity, line.cost_price))
    if not chosen:
        raise ReturnLookupError("Nothing to return.", 400)
    return chosen


@transaction.atomic
def create_purchase_return(shop, *, purchase_id: str, reason: str, items=None) -> PurchaseReturn:
    value = str(purchase_id).strip()
    queryset = Purchase.objects.prefetch_related("items__product").filter(shop=shop)
    if value.isdigit():
        purchase = queryset.filter(pk=int(value)).first()
    else:
        purchase = queryset.filter(reference__iexact=value).first()
    if purchase is None:
        raise ReturnLookupError("Purchase not found", 404)

    chosen = _purchase_lines(purchase, items or [])
    reference = generate_reference("PR", PurchaseReturn, shop=shop)
    amount = Decimal("0")
    stored = []
    try:
        for product_id, quantity, cost in chosen:
            product = Product.objects.select_for_update().get(pk=product_id, shop=shop)
            adjust_stock(
                product,
                -quantity,
                StockTransactionType.RETURN,
                note=f"Purchase return {reference}",
                reference_type="PurchaseReturn",
            )
            amount += quantity * Decimal(cost)
            stored.append({"productId": product.id, "quantity": format(quantity, "f")})
    except ValueError as exc:
        raise ReturnLookupError("Not enough stock to return these goods.", 400) from exc

    return PurchaseReturn.objects.create(
        shop=shop,
        reference=reference,
        purchase=purchase,
        reason=reason,
        amount=quantize_money(amount),
        items=stored,
    )
