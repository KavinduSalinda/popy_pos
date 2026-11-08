"""Notification settings API tests."""

import json
import time
from pathlib import Path

import pytest

from apps.core.choices import ShopPlan
from apps.settings.models import NotificationSettings

from .conftest import authed_client

LOG_PATH = Path(r"c:\Users\USER\Desktop\popy\.cursor\debug-ad6e7c.log")


def _agent_log(hypothesis_id: str, message: str, data: dict, run_id: str = "post-fix"):
    # #region agent log
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "sessionId": "ad6e7c",
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "location": "tests/backend/test_07_settings.py",
                        "message": message,
                        "data": data,
                        "timestamp": time.time() * 1000,
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion


@pytest.mark.django_db
class TestSettingsAPI:
    def test_manager_can_get_shop_notification_settings(self, manager_a, shop_a):
        client = authed_client(manager_a, shop_a)

        response = client.get("/api/settings/notifications")

        # #region agent log
        _agent_log(
            "H1",
            "GET settings response",
            {
                "status": response.status_code,
                "posCheckoutEmailEnabled": response.data.get("posCheckoutEmailEnabled"),
                "proEnabled": response.data.get("proEnabled"),
                "shopPlan": shop_a.plan,
            },
        )
        # #endregion

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

        # #region agent log
        _agent_log(
            "H2",
            "PATCH settings on Pro shop",
            {
                "status": response.status_code,
                "shopPlan": shop_a.plan,
                "bodyKeys": list(response.data.keys()) if hasattr(response, "data") else [],
            },
        )
        # #endregion

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

        # #region agent log
        _agent_log(
            "H2",
            "PATCH settings on Free shop",
            {
                "status": response.status_code,
                "code": response.data.get("code"),
                "shopPlan": shop_a.plan,
            },
        )
        # #endregion

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
