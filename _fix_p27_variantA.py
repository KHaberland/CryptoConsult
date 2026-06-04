"""Чистка портфеля #27 по «варианту A»:
1. Снять дамп ДО — units по wallet, Σ contributions, P&L.
2. Удалить PortfolioContribution id=9 (с items, cascade).
3. НЕ трогать units и WalletTransfer (BTC физически переехал между кошельками,
   HoldingAdjustment id=1 списал лишние units — текущая units-картина корректна).
4. Сверка инварианта Σ WalletHolding.units == PortfolioAsset.units.
5. Снять дамп ПОСЛЕ — те же метрики.

Запускать с явным confirm=True во второй раз; в первый — DRY_RUN.
"""
import os, sys, django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.db import transaction
from portfolios.models import (
    Portfolio, PortfolioContribution, PortfolioContributionItem,
    PortfolioAsset, WalletHolding, HoldingAdjustment,
)
from portfolios.services import WalletLedger
from advisor.services import PortfolioAnalyzer


DRY_RUN = '--confirm' not in sys.argv
TARGET_CONTRIB_ID = 9
PORTFOLIO_ID = 27


def snapshot(label: str):
    print()
    print('=' * 80)
    print(f' SNAPSHOT [{label}]')
    print('=' * 80)
    p = Portfolio.objects.get(pk=PORTFOLIO_ID)
    print(f'Portfolio: #{p.id} {p.name!r}')
    print(f'  initial_amount  = {p.initial_amount}')

    contribs = list(p.contributions.all().order_by('id'))
    contrib_sum = sum((c.amount or Decimal('0')) for c in contribs)
    print(f'  contributions   = {len(contribs)} шт.  Σ={contrib_sum}')
    for c in contribs:
        print(f'     id={c.id}  amount={c.amount}  date={c.contributed_at}')

    print(f'  total_invested  = {(p.initial_amount or 0) + contrib_sum}')

    print('  PortfolioAsset.units / Σ WalletHolding.units:')
    bad = False
    for a in p.assets.all().order_by('symbol'):
        agg = WalletLedger.aggregate_units(p, a.symbol)
        ok = abs(float(a.units or 0) - float(agg)) < 1e-8
        bad = bad or not ok
        print(f'    {a.symbol:>5}  asset.units={a.units}  Σholdings={agg}  {"OK" if ok else "MISMATCH"}')
    print(f'  invariant: {"OK" if not bad else "BROKEN"}')

    try:
        val = PortfolioAnalyzer(p).get_current_value()
        print(f'  legacy P&L:  invested=${val["initial_value"]:,.2f}  '
              f'current=${val["current_value"]:,.2f}  '
              f'P&L=${val["profit_loss"]:+,.2f}  ({val["profit_loss_percent"]:+.2f}%)')
    except Exception as e:
        print(f'  legacy P&L: ERR {e}')

    try:
        fpl = PortfolioAnalyzer(p).get_fiat_pnl('USD')
        print(f'  fiat   P&L:  cash_in=${fpl["cash_in_total"]:,.2f}  '
              f'current=${fpl["current_value"]:,.2f}  '
              f'P&L=${fpl["profit_loss"]:+,.2f}  ({fpl["profit_loss_percent"]:+.2f}%)')
    except Exception as e:
        print(f'  fiat   P&L: ERR {e}')


print(f'== Чистка портфеля #{PORTFOLIO_ID} по варианту A '
      f'({"DRY-RUN" if DRY_RUN else "REAL"}) ==')

snapshot('BEFORE')

try:
    contrib = PortfolioContribution.objects.get(pk=TARGET_CONTRIB_ID)
except PortfolioContribution.DoesNotExist:
    print(f'ERR: PortfolioContribution id={TARGET_CONTRIB_ID} не найден '
          f'— возможно, уже удалён. Прерываюсь.')
    sys.exit(1)

if contrib.portfolio_id != PORTFOLIO_ID:
    print(f'ERR: PortfolioContribution id={TARGET_CONTRIB_ID} принадлежит '
          f'портфелю #{contrib.portfolio_id}, а ожидался #{PORTFOLIO_ID}. '
          f'Прерываюсь.')
    sys.exit(1)

items = list(contrib.items.all())
print()
print(f'Целевая запись:')
print(f'  PortfolioContribution id={contrib.id}  amount={contrib.amount}  '
      f'date={contrib.contributed_at}')
for it in items:
    print(f'     item id={it.id}  {it.symbol} units={it.units} '
          f'price={it.purchase_price} value=${it.value_usd}')

if DRY_RUN:
    print()
    print('DRY-RUN: реальных изменений не будет. Чтобы выполнить:')
    print('   python _fix_p27_variantA.py --confirm')
    sys.exit(0)

with transaction.atomic():
    contrib_pk = contrib.pk
    contrib_amount = contrib.amount
    item_pks = list(contrib.items.values_list('pk', flat=True))
    contrib.delete()
    print()
    print(f'УДАЛЕНО: PortfolioContribution id={contrib_pk} (Σ={contrib_amount})')
    print(f'         + PortfolioContributionItem ids: {item_pks} (cascade)')

snapshot('AFTER')
print()
print('Готово.')
