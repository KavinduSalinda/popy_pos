"""Notification settings API tests."""

import pytest

from apps.core.choices import ShopPlan
from apps.settings.models import NotificationSettings

from .conftest import authed_client


@pytest.mark.django_db
class TestSettingsAPI:
    def test_manager_can_get_shop_notification_settings(self, manager_a, shop_a):
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/settings/notifications")

        assert response.status_code == 200
        # Defaults are off; Free shops can view but feature is not Pro-enabled.
        assert response.data["posCheckoutEmailEnabled"] is False
        assert response.data["proEnabled"] is False

    def test_manager_can_update_shop_notification_settings(self, manager_a, shop_a):
        shop_a.plan = ShopPlan.PRO
        shop_a.save(update_fields=["plan"])
        client = authed_client(manager_a, shop_a)

        response = client.patch(
            "/api/settings/notifications",
            {
                "posCheckoutSmsEnabled": True,
                "lowInventoryAlertPhone": "94771234567",
            },
            format="json",
        )

        assert response.status_code == 200
        assert response.data["posCheckoutSmsEnabled"] is True
        assert response.data["lowInventoryAlertPhone"] == "94771234567"

        settings = NotificationSettings.load(shop_a)
        assert settings.pos_checkout_sms_enabled is True

    def test_free_shop_cannot_update_notification_settings(self, manager_a, shop_a):
        assert shop_a.plan == ShopPlan.FREE
        client = authed_client(manager_a, shop_a)

        response = client.patch(
            "/api/settings/notifications",
            {"posCheckoutSmsEnabled": True},
            format="json",
        )

        assert response.status_code == 403
        assert response.data.get("code") == "PRO_PLAN_REQUIRED"

    def test_settings_are_independent_per_shop(self, manager_a, shop_a, shop_b):
        shop_a.plan = ShopPlan.PRO
        shop_a.save(update_fields=["plan"])
        NotificationSettings.load(shop_a)
        NotificationSettings.load(shop_b)
        client = authed_client(manager_a, shop_a)

        patch = client.patch(
            "/api/settings/notifications",
            {"newCustomerSmsEnabled": True},
            format="json",
        )
        assert patch.status_code == 200

        shop_b_settings = NotificationSettings.load(shop_b)
        assert shop_b_settings.new_customer_sms_enabled is False

    def test_cashier_cannot_access_notification_settings(self, cashier_a, shop_a):
        client = authed_client(cashier_a, shop_a)

        response = client.get("/api/settings/notifications")

        assert response.status_code == 403
