from django.db import models

from apps.core.models import TimeStampedModel
from apps.shops.models import Shop


class ShopInsightSettings(TimeStampedModel):
    """Per-shop Groq key. The full key is never returned by the API."""

    shop = models.OneToOneField(Shop, on_delete=models.CASCADE, related_name="insight_settings")
    groq_api_key = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "insight settings"
        verbose_name_plural = "insight settings"

    def __str__(self):
        return f"Insight settings — {self.shop.name}"
