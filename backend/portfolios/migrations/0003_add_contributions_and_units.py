# Generated manually for contributions and units support

from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


def populate_units_for_existing_assets(apps, schema_editor):
    """Заполняем units для существующих активов."""
    PortfolioAsset = apps.get_model('portfolios', 'PortfolioAsset')
    for asset in PortfolioAsset.objects.filter(units__isnull=True):
        if asset.initial_price and asset.portfolio.initial_amount:
            pct = float(asset.percentage)
            val = float(asset.portfolio.initial_amount) * pct / 100
            price = float(asset.initial_price)
            if price > 0:
                asset.units = Decimal(str(round(val / price, 8)))
                asset.save(update_fields=['units'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('portfolios', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='portfolioasset',
            name='units',
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                max_digits=20,
                null=True,
                verbose_name='Количество единиц'
            ),
        ),
        migrations.CreateModel(
            name='PortfolioContribution',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма взноса ($)')),
                ('contributed_at', models.DateField(auto_now_add=True, verbose_name='Дата взноса')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('portfolio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contributions', to='portfolios.portfolio')),
            ],
            options={
                'verbose_name': 'Взнос в портфель',
                'verbose_name_plural': 'Взносы в портфель',
                'ordering': ['contributed_at'],
            },
        ),
        migrations.RunPython(populate_units_for_existing_assets, noop),
    ]
