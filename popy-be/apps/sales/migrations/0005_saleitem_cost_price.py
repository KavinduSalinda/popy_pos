from decimal import Decimal

from django.db import migrations, models


def backfill_cost_price(apps, schema_editor):
    SaleItem = apps.get_model("sales", "SaleItem")
    Product = apps.get_model("catalog", "Product")
    costs = dict(Product.objects.values_list("id", "cost_price"))
    for item in SaleItem.objects.all().iterator():
        if item.cost_price is None:
            item.cost_price = costs.get(item.product_id) or Decimal("0")
            item.save(update_fields=["cost_price"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_decimal_quantities"),
        ("sales", "0004_decimal_quantities"),
    ]

    operations = [
        migrations.AddField(
            model_name="saleitem",
            name="cost_price",
            field=models.DecimalField(decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(backfill_cost_price, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="saleitem",
            name="cost_price",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
    ]
