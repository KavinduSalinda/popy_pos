from django.db import migrations, models


def set_existing_shops_to_colombo(apps, schema_editor):
    Shop = apps.get_model("shops", "Shop")
    Shop.objects.all().update(timezone="Asia/Colombo")


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0002_plan_and_clock_times"),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="timezone",
            field=models.CharField(default="UTC", max_length=64),
        ),
        migrations.RunPython(set_existing_shops_to_colombo, migrations.RunPython.noop),
    ]
