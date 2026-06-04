from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolios', '0010_fiat_cashflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolio',
            name='manual_usd_eur_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=12,
                null=True,
                verbose_name='Ручной курс USD→EUR для фиатного P&L',
            ),
        ),
    ]
