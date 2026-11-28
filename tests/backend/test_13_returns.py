"""End-to-end sales and purchase return process tests."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Product
from apps.core.choices import Role, StockTransactionType
from apps.inventory.models import StockTransaction
from apps.parties.models import Supplier
from apps.returns.models import PurchaseReturn, SalesReturn
from apps.sales.models import Sale

from .conftest import authed_client


@pytest.fixture
def inventory_officer_a(db, shop_a):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        email="inventory@test.com",
        password="testpass123",
        name="Inventory Officer",
        role=Role.INVENTORY_OFFICER,
        shop=shop_a,
    )


@pytest.fixture
def supplier_a(db, shop_a) -> Supplier:
    return Supplier.objects.create(
        shop=shop_a,
        name="Acme Supplies",
        phone="0770001111",
        email="acme@example.com",
    )


def _create_sale(client, product, *, qty=2, unit_price="5.50", customer_id=None):
    payload = {
        "items": [
            {
                "productId": product.id,
                "quantity": qty,
                "unitPrice": unit_price,
            }
        ],
        "discount": "0.00",
        "tax": "0.00",
        "paymentMethod": "CASH",
        "amountPaid": str(Decimal(unit_price) * qty),
    }
    if customer_id:
        payload["customerId"] = customer_id
    response = client.post("/api/sales", payload, format="json")
    assert response.status_code == 201, response.data
    return response.data


@pytest.mark.django_db
class TestSalesReturnEndToEnd:
    """Sale → stock down → sales return → stock restored → listed."""

    def test_full_sales_return_restores_stock_and_lists(
        self, manager_a, cashier_a, shop_a, product_a, customer_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)

        stock_before_sale = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=3, customer_id=customer_a.id)

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before_sale - 3

        refund = sale["total"]
        response = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "Customer changed mind",
                "refundAmount": refund,
                "items": [],
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["type"] == "SALES"
        assert response.data["saleId"] == sale["id"]
        assert response.data["reason"] == "Customer changed mind"
        assert response.data["refundAmount"] == refund
        assert str(response.data["reference"]).startswith("SR-")
        assert SalesReturn.objects.filter(shop=shop_a, sale_id=sale["id"]).count() == 1

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before_sale

        txs = StockTransaction.objects.filter(
            product=product_a,
            type=StockTransactionType.RETURN,
            reference_type="SalesReturn",
        )
        assert txs.exists()
        assert sum(t.quantity for t in txs) == Decimal("3")

        # Original sale remains unchanged
        sale_row = Sale.objects.get(pk=sale["id"])
        assert sale_row.total == Decimal(refund)

        listed = manager.get("/api/returns")
        assert listed.status_code == 200
        sales_returns = [r for r in listed.data if r.get("type") == "SALES"]
        assert any(r["id"] == response.data["id"] for r in sales_returns)

    def test_partial_sales_return_restores_only_requested_qty(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)

        stock_before = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=4)

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before - 4

        response = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "One unit defective",
                "refundAmount": "5.50",
                "items": [{"productId": product_a.id, "quantity": 1}],
            },
            format="json",
        )
        assert response.status_code == 201, response.data

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before - 3

    def test_full_sales_return_by_reference(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=1)

        response = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["reference"],
                "reason": "Return by receipt number",
                "refundAmount": sale["total"],
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["saleId"] == sale["id"]
        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before

    def test_sale_not_found_returns_404(self, manager_a, shop_a):
        manager = authed_client(manager_a, shop_a)
        response = manager.post(
            "/api/returns/sales",
            {
                "saleId": 999999,
                "reason": "Missing sale",
                "refundAmount": "1.00",
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 404
        assert response.data["message"] == 'No sale, barcode, or SKU found for "999999".'

    def test_cashier_cannot_create_or_list_returns(
        self, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        sale = _create_sale(cashier, product_a, qty=1)

        create = cashier.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "Should fail",
                "refundAmount": "5.50",
                "items": [],
            },
            format="json",
        )
        assert create.status_code == 403

        listed = cashier.get("/api/returns")
        assert listed.status_code == 403

    def test_inventory_officer_can_create_sales_return(
        self, inventory_officer_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        officer = authed_client(inventory_officer_a, shop_a)
        stock_before = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=1)

        response = officer.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "Damaged packaging",
                "refundAmount": "5.50",
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before

    def test_second_full_return_does_not_restock_again(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=2)

        first = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "First return",
                "refundAmount": "11.00",
                "items": [],
            },
            format="json",
        )
        assert first.status_code == 201

        second = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "Second return same sale",
                "refundAmount": "11.00",
                "items": [],
            },
            format="json",
        )
        assert second.status_code == 400, second.data
        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before
        assert SalesReturn.objects.filter(sale_id=sale["id"]).count() == 1

    def test_cross_shop_sale_not_found(
        self, super_admin, cashier_a, shop_a, shop_b, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        sale = _create_sale(cashier, product_a, qty=1)

        # Super admin on shop B cannot return a shop A sale (404, not leak)
        admin_b = authed_client(super_admin, shop_b)
        response = admin_b.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "Wrong shop",
                "refundAmount": "5.50",
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 404

    def test_barcode_and_sku_attach_to_the_newer_sale(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity
        older = _create_sale(cashier, product_a, qty=2)
        newer = _create_sale(cashier, product_a, qty=3)
        Sale.objects.filter(pk=older["id"]).update(created_at=timezone.now() - timedelta(days=2))

        barcode = manager.post(
            "/api/returns/sales",
            {
                "code": product_a.barcode,
                "reason": "Scanned barcode",
                "refundAmount": "5.50",
                "quantity": "1",
            },
            format="json",
        )
        assert barcode.status_code == 201, barcode.data
        assert barcode.data["saleId"] == newer["id"]
        assert barcode.data["items"][0]["productId"] == product_a.id

        sku = manager.post(
            "/api/returns/sales",
            {
                "code": product_a.sku,
                "reason": "Typed SKU",
                "refundAmount": "5.50",
                "quantity": "1",
            },
            format="json",
        )
        assert sku.status_code == 201, sku.data
        assert sku.data["saleId"] == newer["id"]
        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before - 3

    def test_barcode_skips_a_fully_returned_sale(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        older = _create_sale(cashier, product_a, qty=2)
        newer = _create_sale(cashier, product_a, qty=2)
        Sale.objects.filter(pk=older["id"]).update(created_at=timezone.now() - timedelta(days=2))
        full = manager.post(
            "/api/returns/sales",
            {
                "saleId": newer["id"],
                "reason": "Whole newer bill",
                "refundAmount": newer["total"],
                "items": [],
            },
            format="json",
        )
        assert full.status_code == 201, full.data

        response = manager.post(
            "/api/returns/sales",
            {
                "code": product_a.barcode,
                "reason": "Next oldest",
                "refundAmount": "5.50",
                "quantity": "1",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["saleId"] == older["id"]

    def test_unknown_code_and_nothing_left_return_404(self, manager_a, cashier_a, shop_a, product_a):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        unknown = manager.get("/api/returns/sales/lookup", {"code": "NO-SUCH-CODE"})
        assert unknown.status_code == 404

        sale = _create_sale(cashier, product_a, qty=1)
        done = manager.post(
            "/api/returns/sales",
            {
                "saleId": sale["id"],
                "reason": "All back",
                "refundAmount": sale["total"],
                "items": [],
            },
            format="json",
        )
        assert done.status_code == 201, done.data
        lookup = manager.get("/api/returns/sales/lookup", {"code": product_a.sku})
        assert lookup.status_code == 404
        assert lookup.data["message"] == "No returnable sale for this item."

    def test_quantity_above_remaining_is_rejected(self, manager_a, cashier_a, shop_a, product_a):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        _create_sale(cashier, product_a, qty=1)
        response = manager.post(
            "/api/returns/sales",
            {
                "code": product_a.barcode,
                "reason": "Too many",
                "refundAmount": "20.00",
                "quantity": "2",
            },
            format="json",
        )
        assert response.status_code == 400, response.data
        assert response.data["message"] == "Quantity is higher than what is left to return."

    def test_bill_reference_wins_when_the_text_is_also_a_sku(
        self, manager_a, cashier_a, shop_a, product_a
    ):
        cashier = authed_client(cashier_a, shop_a)
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity
        sale = _create_sale(cashier, product_a, qty=2)
        product_a.sku = sale["reference"]
        product_a.save(update_fields=["sku"])

        response = manager.post(
            "/api/returns/sales",
            {
                "code": sale["reference"],
                "reason": "Bill wins",
                "refundAmount": sale["total"],
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["saleId"] == sale["id"]
        assert response.data["items"] == []
        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before


@pytest.mark.django_db
class TestPurchaseReturnEndToEnd:
    """Purchase receive → stock up → purchase return → stock down → listed."""

    def test_full_purchase_return_reduces_stock(
        self, manager_a, shop_a, product_a, supplier_a
    ):
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity

        create = manager.post(
            "/api/purchases",
            {
                "supplierId": supplier_a.id,
                "status": "RECEIVED",
                "items": [
                    {
                        "productId": product_a.id,
                        "quantity": 5,
                        "costPrice": "3.00",
                    }
                ],
            },
            format="json",
        )
        assert create.status_code == 201, create.data
        purchase_id = create.data["id"]

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before + 5

        response = manager.post(
            "/api/returns/purchase",
            {
                "purchaseId": purchase_id,
                "reason": "Wrong items from supplier",
                "amount": "15.00",
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["type"] == "PURCHASE"
        assert response.data["purchaseId"] == purchase_id
        assert str(response.data["reference"]).startswith("PR-")
        assert PurchaseReturn.objects.filter(shop=shop_a, purchase_id=purchase_id).count() == 1

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before

        listed = manager.get("/api/returns")
        assert listed.status_code == 200
        purchase_returns = [r for r in listed.data if r.get("type") == "PURCHASE"]
        assert any(r["id"] == response.data["id"] for r in purchase_returns)

    def test_purchase_not_found_returns_404(self, manager_a, shop_a):
        manager = authed_client(manager_a, shop_a)
        response = manager.post(
            "/api/returns/purchase",
            {
                "purchaseId": 999999,
                "reason": "Missing",
                "amount": "1.00",
                "items": [],
            },
            format="json",
        )
        assert response.status_code == 404
        assert response.data["message"] == "Purchase not found"

    def test_partial_purchase_return(self, manager_a, shop_a, product_a, supplier_a):
        manager = authed_client(manager_a, shop_a)
        stock_before = product_a.stock_quantity

        create = manager.post(
            "/api/purchases",
            {
                "supplierId": supplier_a.id,
                "status": "RECEIVED",
                "items": [
                    {
                        "productId": product_a.id,
                        "quantity": 10,
                        "costPrice": "2.00",
                    }
                ],
            },
            format="json",
        )
        assert create.status_code == 201, create.data

        response = manager.post(
            "/api/returns/purchase",
            {
                "purchaseId": create.data["id"],
                "reason": "Return 3 units",
                "amount": "6.00",
                "items": [{"productId": product_a.id, "quantity": 3}],
            },
            format="json",
        )
        assert response.status_code == 201, response.data

        product_a.refresh_from_db()
        assert product_a.stock_quantity == stock_before + 7
