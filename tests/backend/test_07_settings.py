"""Notification settings API tests."""

import pytest
from django.test import override_settings

from apps.core.choices import ShopPlan
from apps.core.notifications.service import (
    notify_low_inventory,
    notify_new_customer,
    notify_new_user,
    notify_pos_checkout,
)
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
        assert response.data["channelsAvailable"] is False

    def test_manager_can_update_shop_notification_settings(self, manager_a, shop_a):
        shop_a.plan = ShopPlan.PRO
        shop_a.save(update_fields=["plan"])
        client = authed_client(manager_a, shop_a)

        viewed = client.get("/api/settings/notifications")
        assert viewed.status_code == 200
        assert viewed.data["proEnabled"] is True
        assert viewed.data["channelsAvailable"] is True

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

    @override_settings(NOTIFICATIONS_ENABLED=False)
    def test_desktop_blocks_email_and_sms_even_for_a_pro_shop(
        self, manager_a, shop_a, cashier_a, customer_a, product_a, monkeypatch
    ):
        shop_a.plan = ShopPlan.PRO
        shop_a.save(update_fields=["plan"])
        settings = NotificationSettings.load(shop_a)
        settings.pos_checkout_email_enabled = True
        settings.pos_checkout_sms_enabled = True
        settings.pos_checkout_cashier_email_enabled = True
        settings.pos_checkout_cashier_sms_enabled = True
        settings.new_customer_email_enabled = True
        settings.low_inventory_email_enabled = True
        settings.new_user_email_enabled = True
        settings.save()

        sent = []
        monkeypatch.setattr(
            "apps.core.notifications.service.send_email",
            lambda **kwargs: sent.append(kwargs) or True,
        )
        monkeypatch.setattr(
            "apps.core.notifications.service.send_sms",
            lambda **kwargs: sent.append(kwargs) or True,
        )

        class Untouched:
            def __getattr__(self, name):
                raise AssertionError(name)

        notify_pos_checkout(Untouched(), send_email=True, send_sms=True, user=cashier_a)
        notify_low_inventory(product_a)
        notify_new_customer(customer_a)
        notify_new_user(manager_a, temporary_password="secret")
        assert sent == []

        client = authed_client(manager_a, shop_a)
        viewed = client.get("/api/settings/notifications")
        assert viewed.status_code == 200
        assert viewed.data["proEnabled"] is True
        assert viewed.data["channelsAvailable"] is False

        saved = client.patch(
            "/api/settings/notifications",
            {"posCheckoutSmsEnabled": False},
            format="json",
        )
        assert saved.status_code == 403
        assert saved.data.get("code") == "NOTIFICATIONS_UNAVAILABLE"
        settings.refresh_from_db()
        assert settings.pos_checkout_sms_enabled is True

        checkout = authed_client(cashier_a, shop_a).get(
            "/api/settings/pos-checkout-notifications"
        )
        assert checkout.status_code == 200
        assert checkout.data["canSendEmail"] is False
        assert checkout.data["canSendSms"] is False
        assert checkout.data["emailEnabled"] is False
        assert checkout.data["smsEnabled"] is False
        assert checkout.data["proEnabled"] is True
        assert checkout.data["channelsAvailable"] is False

    def test_pro_shop_sends_email_when_notifications_are_on(
        self, shop_a, customer_a, monkeypatch
    ):
        shop_a.plan = ShopPlan.PRO
        shop_a.save(update_fields=["plan"])
        settings = NotificationSettings.load(shop_a)
        settings.new_customer_email_enabled = True
        settings.save()
        sent = []
        monkeypatch.setattr(
            "apps.core.notifications.service.send_email",
            lambda **kwargs: sent.append(kwargs) or True,
        )

        notify_new_customer(customer_a)

        assert len(sent) == 1
        assert sent[0]["to_email"] == customer_a.email

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
