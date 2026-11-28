"""Dashboard and reports API smoke tests."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import Product
from apps.core.choices import Role
from apps.dashboard.services import _bounds
from apps.returns.models import SalesReturn
from apps.sales.models import Sale, SaleItem

from .conftest import authed_client


def _worked_sale(shop, cashier, product, reference="INV-W"):
    sale = Sale.objects.create(
        shop=shop,
        reference=reference,
        subtotal=Decimal("12.00"),
        discount=Decimal("1.00"),
        tax=Decimal("0"),
        total=Decimal("11.00"),
        payment_method="CASH",
        cashier=cashier,
    )
    SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=Decimal("2"),
        unit_price=Decimal("5.50"),
    )
    return sale


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
        assert body["kpis"]["totalSales"]["current"] == 8.5
        assert body["kpis"]["transactions"]["current"] == 1
        assert body["kpis"]["averageOrderValue"]["current"] == 8.5
        assert body["kpis"]["grossProfit"]["current"] == 3.09
        assert body["kpis"]["itemsPerTransaction"]["current"] == 1.5
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

    def test_window_uses_the_shop_timezone(self, shop_a):
        shop_a.timezone = "Asia/Colombo"
        shop_a.save(update_fields=["timezone"])

        bounds = _bounds(shop_a, 7)

        zone = ZoneInfo("Asia/Colombo")
        local_start = bounds["current_start"].astimezone(zone)
        assert local_start.hour == 0
        assert local_start.minute == 0
        assert bounds["current_end"] - bounds["current_start"] == timedelta(days=7)
        assert bounds["prev_end"] == bounds["current_start"]
        assert bounds["current_start"] - bounds["prev_start"] == timedelta(days=7)

    def test_refund_of_an_older_sale_reduces_this_period(self, manager_a, shop_a, cashier_a, product_a):
        sale = _worked_sale(shop_a, cashier_a, product_a, "INV-OLD")
        sale.created_at = timezone.now() - timedelta(days=40)
        sale.save(update_fields=["created_at"])
        SalesReturn.objects.create(
            shop=shop_a,
            reference="RET-OLD",
            sale=sale,
            reason="Late",
            refund_amount=Decimal("2.50"),
            items=[],
        )
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/dashboard/overview?days=7")

        kpis = response.data["kpis"]
        assert kpis["totalSales"]["current"] == -2.5
        assert kpis["transactions"]["current"] == 0
        assert kpis["averageOrderValue"]["current"] == 0
        assert kpis["itemsPerTransaction"]["current"] == 0
        assert kpis["grossProfit"]["current"] == -0.91
        assert kpis["refunds"]["current"] == 2.5

    def test_refund_larger_than_the_sale_is_capped(self, manager_a, shop_a, cashier_a, product_a):
        sale = _worked_sale(shop_a, cashier_a, product_a, "INV-CAP")
        SalesReturn.objects.create(
            shop=shop_a,
            reference="RET-CAP",
            sale=sale,
            reason="Too much",
            refund_amount=Decimal("50.00"),
            items=[],
        )
        client = authed_client(manager_a, shop_a)

        kpis = client.get("/api/dashboard/overview?days=7").data["kpis"]

        assert kpis["totalSales"]["current"] == 0
        assert kpis["refunds"]["current"] == 11
        assert kpis["grossProfit"]["current"] == 0
        assert kpis["transactions"]["current"] == 1

    def test_second_refund_only_takes_the_remainder(self, manager_a, shop_a, cashier_a, product_a):
        sale = _worked_sale(shop_a, cashier_a, product_a, "INV-TWO")
        SalesReturn.objects.create(
            shop=shop_a,
            reference="RET-1",
            sale=sale,
            reason="First",
            refund_amount=Decimal("8.00"),
            items=[],
        )
        SalesReturn.objects.create(
            shop=shop_a,
            reference="RET-2",
            sale=sale,
            reason="Second",
            refund_amount=Decimal("10.00"),
            items=[],
        )
        client = authed_client(manager_a, shop_a)

        kpis = client.get("/api/dashboard/overview?days=7").data["kpis"]

        assert kpis["totalSales"]["current"] == 0
        assert kpis["refunds"]["current"] == 11
        assert kpis["grossProfit"]["current"] == 0

    def test_later_cost_edit_does_not_change_profit(self, manager_a, shop_a, cashier_a, product_a):
        sale = Sale.objects.create(
            shop=shop_a,
            reference="INV-COST",
            subtotal=Decimal("11.00"),
            discount=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("11.00"),
            payment_method="CASH",
            cashier=cashier_a,
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=product_a,
            quantity=Decimal("2"),
            unit_price=Decimal("5.50"),
        )
        assert item.cost_price == Decimal("3.00")
        product_a.cost_price = Decimal("9.00")
        product_a.save(update_fields=["cost_price"])
        client = authed_client(manager_a, shop_a)

        kpis = client.get("/api/dashboard/overview?days=7").data["kpis"]

        assert kpis["grossProfit"]["current"] == 5
        assert kpis["totalSales"]["current"] == 11

    def test_oversize_discount_does_not_reduce_sales_below_zero(self, manager_a, shop_a, cashier_a, product_a):
        sale = Sale.objects.create(
            shop=shop_a,
            reference="INV-DISC",
            subtotal=Decimal("11.00"),
            discount=Decimal("100.00"),
            tax=Decimal("0"),
            total=Decimal("-89.00"),
            payment_method="CASH",
            cashier=cashier_a,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product_a,
            quantity=Decimal("1"),
            unit_price=Decimal("11.00"),
        )
        client = authed_client(manager_a, shop_a)

        kpis = client.get("/api/dashboard/overview?days=7").data["kpis"]

        assert kpis["totalSales"]["current"] == 0
        assert kpis["grossProfit"]["current"] == -3
        assert kpis["transactions"]["current"] == 1

    def test_items_per_transaction_rounds_half_up(self, manager_a, shop_a, cashier_a, product_a):
        sale = Sale.objects.create(
            shop=shop_a,
            reference="INV-QTY",
            subtotal=Decimal("5.00"),
            discount=Decimal("0"),
            tax=Decimal("0"),
            total=Decimal("5.00"),
            payment_method="CASH",
            cashier=cashier_a,
        )
        SaleItem.objects.create(
            sale=sale,
            product=product_a,
            quantity=Decimal("1.25"),
            unit_price=Decimal("4.00"),
        )
        client = authed_client(manager_a, shop_a)

        kpis = client.get("/api/dashboard/overview?days=7").data["kpis"]

        assert kpis["itemsPerTransaction"]["current"] == 1.3

    def test_cashier_cannot_load_reports(self, cashier_a, shop_a):
        client = authed_client(cashier_a, shop_a)

        response = client.get("/api/reports/sales")

        assert response.status_code == 403

    def test_cashier_and_inventory_officer_cannot_open_the_dashboard(
        self, cashier_a, manager_a, shop_a
    ):
        officer = get_user_model().objects.create_user(
            email="inventory-dashboard@test.com",
            password="testpass123",
            name="Inventory Officer",
            role=Role.INVENTORY_OFFICER,
            shop=shop_a,
        )

        cashier = authed_client(cashier_a, shop_a)
        assert cashier.get("/api/dashboard/overview").status_code == 403
        assert cashier.get("/api/categories").status_code == 403

        officer_client = authed_client(officer, shop_a)
        assert officer_client.get("/api/dashboard/overview").status_code == 403

        manager = authed_client(manager_a, shop_a)
        assert manager.get("/api/dashboard/overview").status_code == 200
