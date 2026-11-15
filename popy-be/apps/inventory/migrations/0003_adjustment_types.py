from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_decimal_quantities"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stockadjustment",
            name="adjustment_type",
            field=models.CharField(
                choices=[
                    ("DAMAGE", "Damage"),
                    ("LOSS", "Loss"),
                    ("EXPIRE", "Expire"),
                    ("FOUND", "Found"),
                    ("ADD", "Add"),
                ],
                max_length=20,
            ),
        ),
    ]
