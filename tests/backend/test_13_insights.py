"""Insights report math and Groq wiring. Groq itself is mocked."""

import json
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.catalog.models import Category, Product
from apps.insights.models import ShopInsightSettings
from apps.sales.models import Sale, SaleItem

from .conftest import authed_client


def _sale(shop, cashier, product, quantity, reference):
    sale = Sale.objects.create(
        shop=shop,
        reference=reference,
        subtotal=0,
        total=0,
        payment_method="CASH",
        cashier=cashier,
    )
    SaleItem.objects.create(
        sale=sale,
        product=product,
        quantity=Decimal(quantity),
        unit_price=Decimal("5.50"),
        total=Decimal("0"),
    )
    return sale


class FakeGroq:
    def __init__(self, content):
        self.content = content
        self.requests = []

    def __call__(self, request, timeout=30):
        self.requests.append(request)
        payload = self.content
        outer = {"choices": [{"message": {"content": payload}}]}

        class Response:
            def read(self):
                return json.dumps(outer).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Response()


def test_plain_reply_drops_markdown_and_field_names():
    from apps.insights.groq import plain_reply

    text = plain_reply(
        '1. **Purchasing** – buy **30** units (the "buy90" figure).\n* per_day is 0.333'
    )

    assert "**" not in text
    assert "buy90" not in text
    assert "per_day" not in text
    assert text.startswith("Purchasing")
    assert plain_reply("{}") == ""


def test_validation_message_skips_empty_history_items():
    from apps.insights.views import _validation_message

    message = _validation_message(
        {"history": [{}, {"content": ["This earlier reply is too long to resend."]}]}
    )

    assert message == "This earlier reply is too long to resend."
    assert message != "{}"


@pytest.mark.django_db
class TestInsightRequirements:
    def test_estimates_units_to_buy_for_7_30_and_90_days(
        self, manager_a, shop_a, category_a, product_a
    ):
        product_a.stock_quantity = 10
        product_a.save(update_fields=["stock_quantity"])
        _sale(shop_a, manager_a, product_a, 30, "S-TEA")
        Product.objects.create(
            shop=shop_a,
            category=category_a,
            name="Still Water",
            sku="WATER-1",
            unit="btl",
            cost_price="1.00",
            selling_price="2.00",
            stock_quantity=4,
            status=True,
        )
        Product.objects.create(
            shop=shop_a,
            category=category_a,
            name="Old Biscuit",
            sku="BISC-1",
            unit="pkt",
            cost_price="1.00",
            selling_price="2.00",
            stock_quantity=8,
            status=False,
        )

        response = authed_client(manager_a, shop_a).get("/api/insights/requirements")

        assert response.status_code == 200
        rows = {row["product"]: row for row in response.data["rows"]}
        assert "Old Biscuit" not in rows
        tea = rows["Green Tea"]
        assert tea["soldLast30"] == 30
        assert tea["need7"] == 7
        assert tea["need30"] == 30
        assert tea["need90"] == 90
        assert tea["buy7"] == 0
        assert tea["buy30"] == 20
        assert tea["buy90"] == 80
        water = rows["Still Water"]
        assert water["need7"] == 0
        assert water["need30"] == 0
        assert water["need90"] == 0
        assert water["buy7"] == 0
        assert water["buy30"] == 0
        assert water["buy90"] == 0
        assert response.data["summary"]["buy30"] == 20
        assert response.data["summary"]["buy90"] == 80

    def test_report_hides_another_shops_product(
        self, manager_a, shop_a, shop_b, product_a
    ):
        category = Category.objects.create(shop=shop_b, name="Other")
        Product.objects.create(
            shop=shop_b,
            category=category,
            name="Other Shop Soap",
            sku="SOAP-B",
            unit="bar",
            cost_price="1.00",
            selling_price="2.00",
            stock_quantity=3,
        )

        response = authed_client(manager_a, shop_a).get("/api/insights/requirements")

        names = [row["product"] for row in response.data["rows"]]
        assert "Other Shop Soap" not in names
        assert "Green Tea" in names

    def test_cashier_cannot_view_the_report(self, cashier_a, shop_a):
        response = authed_client(cashier_a, shop_a).get("/api/insights/requirements")

        assert response.status_code == 403

    @override_settings(GROQ_API_KEY="")
    def test_missing_key_still_returns_the_report_and_does_not_call_groq(
        self, manager_a, shop_a, monkeypatch
    ):
        def explode(*args, **kwargs):
            raise AssertionError("Groq should not be called")

        monkeypatch.setattr("apps.insights.groq.urlopen", explode)
        client = authed_client(manager_a, shop_a)

        report = client.get("/api/insights/requirements")
        writing = client.post("/api/insights/summary", {}, format="json")

        assert report.status_code == 200
        assert writing.status_code == 400
        assert writing.data["code"] == "AI_NOT_CONFIGURED"

    @override_settings(GROQ_API_KEY="gsk_env_should_not_win")
    def test_summary_and_question_use_the_shop_key(
        self, manager_a, shop_a, shop_b, product_a, monkeypatch
    ):
        category = Category.objects.create(shop=shop_b, name="Other")
        Product.objects.create(
            shop=shop_b,
            category=category,
            name="Other Shop Soap",
            sku="SOAP-B",
            unit="bar",
            cost_price="1.00",
            selling_price="2.00",
        )
        ShopInsightSettings.objects.create(shop=shop_a, groq_api_key="gsk_shop_key_123456")
        fake = FakeGroq(
            json.dumps(
                {
                    "summary": "Tea sold steadily.",
                    "prediction": "Buy 20 units of tea for 30 days.",
                }
            )
        )
        monkeypatch.setattr("apps.insights.groq.urlopen", fake)
        client = authed_client(manager_a, shop_a)

        summary = client.post("/api/insights/summary", {}, format="json")
        answer = client.post(
            "/api/insights/ask",
            {"question": "What should I buy for 90 days?", "history": []},
            format="json",
        )

        assert summary.status_code == 200
        assert summary.data["summary"] == "Tea sold steadily."
        assert summary.data["prediction"] == "Buy 20 units of tea for 30 days."
        assert answer.status_code == 200
        assert answer.data["answer"]
        assert "**" not in answer.data["answer"]
        bodies = [request.data.decode() for request in fake.requests]
        assert any("What should I buy for 90 days?" in body for body in bodies)
        assert all("Other Shop Soap" not in body for body in bodies)
        assert all("gsk_shop_key_123456" not in body for body in bodies)
        assert fake.requests[-1].get_header("Authorization") == "Bearer gsk_shop_key_123456"
        assert fake.requests[-1].get_header("User-agent") == "PopyPOS/1.0"
        sent = json.loads(fake.requests[0].data.decode())
        assert sent["model"] == "openai/gpt-oss-120b"

    @override_settings(GROQ_API_KEY="")
    def test_a_long_earlier_reply_is_shortened_instead_of_braces(
        self, manager_a, shop_a, monkeypatch
    ):
        ShopInsightSettings.objects.create(shop=shop_a, groq_api_key="gsk_shop_key_123456")
        fake = FakeGroq("Hello. Ask what to buy for the next 90 days.")
        monkeypatch.setattr("apps.insights.groq.urlopen", fake)
        essay = ("Buy 30 units of cheese. " * 80) + "UNIQUE_TAIL_MARKER"

        response = authed_client(manager_a, shop_a).post(
            "/api/insights/ask",
            {
                "question": "hi",
                "history": [
                    {"role": "user", "content": "give a 90 day plan for me"},
                    {"role": "assistant", "content": essay},
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["answer"] == "Hello. Ask what to buy for the next 90 days."
        sent = json.loads(fake.requests[0].data.decode())
        prior = sent["messages"][2]["content"]
        assert len(prior) == 1000
        assert "UNIQUE_TAIL_MARKER" not in prior

    @override_settings(GROQ_API_KEY="gsk_env_key_123456")
    def test_env_key_is_used_when_the_shop_has_none(self, manager_a, shop_a, monkeypatch):
        fake = FakeGroq(json.dumps({"summary": "Quiet shop.", "prediction": "Nothing to buy."}))
        monkeypatch.setattr("apps.insights.groq.urlopen", fake)

        response = authed_client(manager_a, shop_a).post("/api/insights/summary", {}, format="json")

        assert response.status_code == 200
        assert fake.requests[0].get_header("Authorization") == "Bearer gsk_env_key_123456"
