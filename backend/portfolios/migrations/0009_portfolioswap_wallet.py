# Миграция: добавление FK wallet в PortfolioSwap.
# Реализация по плану PLAN06-realization.md (Агент 12).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('portfolios', '0008_backfill_default_wallet'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolioswap',
            name='wallet',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='swaps',
                to='portfolios.wallet',
                verbose_name='Кошелёк',
            ),
        ),
    ]
