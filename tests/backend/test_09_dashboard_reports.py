"""Dashboard and reports API smoke tests."""

from decimal import Decimal

import pytest

from apps.catalog.models import Product
from apps.returns.models import SalesReturn
from apps.sales.models import Sale, SaleItem

from .conftest import authed_client


@pytest.mark.django_db
class TestDashboardAndReportsAPI:
    def test_manager_can_load_dashboard_summary(self, manager_a, shop_a):
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200
        assert isinstance(response.data, dict)

    def test_manager_can_load_sales_report(self, manager_a, shop_a):
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/reports/sales")

        assert response.status_code == 200

    def test_manager_can_load_inventory_report(self, manager_a, shop_a, product_a):
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/reports/inventory")

        assert response.status_code == 200

    def test_overview_uses_the_selected_range(self, manager_a, shop_a, cashier_a, product_a, category_a):
        Product.objects.create(
            shop=shop_a,
            category=category_a,
            name="Empty Shelf",
            sku="EMPTY-SHELF",
            unit="pcs",
            cost_price=Decimal("1.00"),
            selling_price=Decimal("2.00"),
            reorder_level=4,
            stock_quantity=0,
            status=True,
        )
        sale = Sale.objects.create(
            shop=shop_a,
            reference="INV-1",
            subtotal=Decimal("12.00"),
            discount=Decimal("1.00"),
            tax=Decimal("0"),
            total=Decimal("11.00"),
            payment_method="CASH",
            cashier=cashier_a,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product_a,
            quantity=Decimal("2"),
            unit_price=Decimal("5.50"),
        )
        SalesReturn.objects.create(
            shop=shop_a,
            reference="RET-1",
            sale=sale,
            reason="Damaged",
            refund_amount=Decimal("2.50"),
            items=[],
        )
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/dashboard/overview?days=7")

        assert response.status_code == 200
        body = response.data
        assert body["days"] == 7
        assert body["kpis"]["totalSales"]["current"] == 11.0
        assert body["kpis"]["transactions"]["current"] == 1
        assert body["kpis"]["grossProfit"]["current"] == 5.0
        assert body["kpis"]["refunds"]["current"] == 2.5
        assert len(body["salesTrend"]) == 7
        assert body["categories"][0]["category"] == "Beverages"
        assert body["paymentMethods"][0]["method"] == "Cash"
        assert body["salesByCashier"][0]["name"] == "Shop Cashier"
        assert body["topProducts"][0]["name"] == "Green Tea"
        assert sum(point["discounts"] for point in body["discountsAndRefunds"]) == 1.0
        assert sum(point["refunds"] for point in body["discountsAndRefunds"]) == 2.5
        assert any(row["name"] == "Empty Shelf" and row["status"] == "out" for row in body["lowStock"])
        assert body["recentSales"][0]["reference"] == "INV-1"
        assert sum(point["total"] for point in body["salesByHour"]) == 11.0

    def test_cashier_cannot_load_reports(self, cashier_a, shop_a):
        client = authed_client(cashier_a, shop_a)

        response = client.get("/api/reports/sales")

        assert response.status_code == 403
