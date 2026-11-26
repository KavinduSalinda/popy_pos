from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("shops", "0002_plan_and_clock_times"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopInsightSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("groq_api_key", models.CharField(blank=True, default="", max_length=200)),
                (
                    "shop",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insight_settings",
                        to="shops.shop",
                    ),
                ),
            ],
            options={
                "verbose_name": "insight settings",
                "verbose_name_plural": "insight settings",
            },
        ),
    ]
