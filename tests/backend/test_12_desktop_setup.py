"""Desktop first-run setup is local-only and runs once."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.choices import ShopPlan
from apps.core.desktop_setup import promote_desktop_shops_to_pro
from apps.shops.models import Shop


@pytest.mark.django_db
class TestDesktopSetup:
    def test_health_hides_setup_unless_the_desktop_flag_is_on(self, monkeypatch):
        monkeypatch.delenv("POPY_ENABLE_DESKTOP_SETUP", raising=False)
        client = APIClient()

        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["needsSetup"] is False

    def test_setup_creates_the_shop_once_from_this_computer(self, monkeypatch):
        monkeypatch.setenv("POPY_ENABLE_DESKTOP_SETUP", "1")
        client = APIClient()
        payload = {
            "shopName": "Popy Market",
            "adminName": "Shop Owner",
            "email": "owner@shop.test",
            "password": "Shopkeeper1",
        }

        created = client.post("/api/setup", payload, format="json")

        assert created.status_code == 201
        assert User.objects.filter(email="owner@shop.test", is_superuser=True).exists()
        assert Shop.objects.get(name="Popy Market").plan == ShopPlan.PRO

        health = client.get("/api/health")
        assert health.json()["needsSetup"] is False

        again = client.post("/api/setup", payload, format="json")
        assert again.status_code == 409

    def test_setup_rejects_other_computers(self, monkeypatch):
        monkeypatch.setenv("POPY_ENABLE_DESKTOP_SETUP", "1")
        client = APIClient()

        response = client.post(
            "/api/setup",
            {
                "shopName": "Popy Market",
                "adminName": "Shop Owner",
                "email": "owner@shop.test",
                "password": "Shopkeeper1",
            },
            format="json",
            REMOTE_ADDR="8.8.8.8",
        )

        assert response.status_code == 403
        assert User.objects.count() == 0

    def test_setup_is_closed_on_a_normal_server(self, monkeypatch):
        monkeypatch.delenv("POPY_ENABLE_DESKTOP_SETUP", raising=False)
        client = APIClient()

        response = client.post(
            "/api/setup",
            {
                "shopName": "Popy Market",
                "adminName": "Shop Owner",
                "email": "owner@shop.test",
                "password": "Shopkeeper1",
            },
            format="json",
        )

        assert response.status_code == 404

    def test_desktop_start_marks_existing_shops_pro(self, shop_a):
        assert shop_a.plan == ShopPlan.FREE

        promote_desktop_shops_to_pro()

        shop_a.refresh_from_db()
        assert shop_a.plan == ShopPlan.PRO
