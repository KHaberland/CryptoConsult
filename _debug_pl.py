"""Диагностика прибыли/убытка активного портфеля.

Запуск:
    cd backend
    python ../_debug_pl.py
"""
import os
import sys
import django

# Чтобы запустить Django ORM без manage.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from portfolios.models import (
    Portfolio, PortfolioAsset, PortfolioContribution,
    PortfolioContributionItem, PortfolioWithdrawal,
    PortfolioSwap, Wallet, WalletHolding, WalletTransfer,
    HoldingAdjustment,
)
from portfolios.services import PriceService
from advisor.services import PortfolioAnalyzer


def fmt(x, w=14):
    if x is None:
        return f"{'-':>{w}}"
    if isinstance(x, (int, float, Decimal)):
        return f"{float(x):>{w},.4f}"
    return f"{str(x):>{w}}"


print("=" * 100)
print("ВСЕ ПОРТФЕЛИ В БД")
print("=" * 100)
qs = Portfolio.objects.all().order_by('-is_active', '-created_at')
for p in qs:
    print(f"  id={p.id}  active={p.is_active}  imported={p.is_imported}  "
          f"name={p.name!r}  initial_amount={p.initial_amount}  "
          f"session={p.session_id[:8]}...  created={p.created_at}")

active_portfolios = list(Portfolio.objects.filter(is_active=True))
print()
print(f"Активных портфелей: {len(active_portfolios)}")

for portfolio in active_portfolios:
    print()
    print("#" * 100)
    print(f"# ПОРТФЕЛЬ id={portfolio.id}  «{portfolio.name}»")
    print("#" * 100)

    print(f"  initial_amount (Portfolio.initial_amount) = {portfolio.initial_amount}")
    print(f"  is_imported = {portfolio.is_imported}")
    print(f"  start_date  = {portfolio.start_date}")
    print(f"  target_date = {portfolio.target_date}")

    contribs = list(portfolio.contributions.all().order_by('contributed_at'))
    print()
    print(f"  PortfolioContribution ({len(contribs)} шт.):")
    contrib_sum = Decimal('0')
    for c in contribs:
        print(f"    id={c.id}  amount={c.amount}  contributed_at={c.contributed_at}")
        items = list(c.items.all())
        for it in items:
            print(f"       └─ {it.symbol}: units={it.units}  "
                  f"price={it.purchase_price}  value_usd={it.value_usd}")
        contrib_sum += c.amount or Decimal('0')
    print(f"    Σ contributions.amount = {contrib_sum}")

    withdrawals = list(portfolio.withdrawals.all())
    print()
    print(f"  PortfolioWithdrawal ({len(withdrawals)} шт.):")
    wsum = Decimal('0')
    for w in withdrawals:
        print(f"    id={w.id}  amount={w.amount}  value_after={w.value_after}  "
              f"withdrawn_at={w.withdrawn_at}")
        wsum += w.amount or Decimal('0')
    print(f"    Σ withdrawals.amount = {wsum}")

    print()
    print(f"  Total invested (initial_amount + Σ contributions) = "
          f"{float(portfolio.initial_amount or 0) + float(contrib_sum):.2f}")

    assets = list(portfolio.assets.all())
    symbols = [a.symbol for a in assets]
    try:
        prices = PriceService().get_prices(symbols)
    except Exception as e:
        print(f"  [WARN] не удалось получить цены: {e}")
        prices = {}

    print()
    print(f"  PortfolioAsset ({len(assets)} шт.):")
    header = (f"    {'symbol':>8} {'%':>7} {'units':>16} {'init_price':>14} "
              f"{'cur_price':>14} {'init_val (%)':>14} {'cur_val':>14} "
              f"{'P/L':>12} {'P/L %':>10}")
    print(header)
    total_invested = float(portfolio.initial_amount or 0) + float(contrib_sum)
    sum_current = 0.0
    sum_initial_by_pct = 0.0
    sum_initial_by_units = 0.0
    for a in assets:
        cur_price = float(prices.get(a.symbol) or 0)
        units = float(a.units or 0)
        init_price = float(a.initial_price or 0)
        cur_val = units * cur_price
        init_val_pct = total_invested * float(a.percentage or 0) / 100
        init_val_units = units * init_price
        pl = cur_val - init_val_pct
        pl_pct = (pl / init_val_pct * 100) if init_val_pct > 0 else 0
        sum_current += cur_val
        sum_initial_by_pct += init_val_pct
        sum_initial_by_units += init_val_units
        print(f"    {a.symbol:>8} {float(a.percentage):>7.2f} "
              f"{units:>16.8f} {init_price:>14.4f} {cur_price:>14.4f} "
              f"{init_val_pct:>14.2f} {cur_val:>14.2f} "
              f"{pl:>12.2f} {pl_pct:>10.2f}")

    print()
    print(f"  Σ current_value (units × cur_price) = {sum_current:.2f}")
    print(f"  Σ initial_value (по % от total_invested) = {sum_initial_by_pct:.2f}")
    print(f"  Σ initial_value (по units × initial_price) = {sum_initial_by_units:.2f}")

    print()
    print("  ── Метрики из PortfolioAnalyzer.get_current_value() ──")
    try:
        value = PortfolioAnalyzer(portfolio).get_current_value()
        print(f"    initial_value (= total_invested) = {value['initial_value']:.2f}")
        print(f"    current_value = {value['current_value']:.2f}")
        print(f"    profit_loss   = {value['profit_loss']:.2f}")
        print(f"    profit_loss_% = {value['profit_loss_percent']:.2f}%")
        print()
        print(f"    Δ (cur - invested) = {value['current_value'] - value['initial_value']:.2f}")
        print(f"    Δ (cur - Σunits*init_price) = "
              f"{value['current_value'] - sum_initial_by_units:.2f}")
    except Exception as e:
        print(f"    [ERR] {e}")

    wallets = list(Wallet.objects.filter(portfolio=portfolio).prefetch_related('holdings'))
    print()
    print(f"  Wallets ({len(wallets)} шт.):")
    for w in wallets:
        print(f"    id={w.id}  name={w.name!r}  default={w.is_default}")
        for h in w.holdings.all():
            print(f"       └─ {h.symbol}: units={h.units}")
