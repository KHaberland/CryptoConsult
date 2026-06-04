"""Глубокая диагностика портфеля id=27."""
import os
import sys
import django

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

p = Portfolio.objects.get(pk=27)
print(f"Portfolio: id={p.id} name={p.name!r}")
print(f"  initial_amount = {p.initial_amount}")
print(f"  is_imported = {p.is_imported}")
print(f"  start_date = {p.start_date}")

print()
print("=== Все взносы (PortfolioContribution + items) ===")
for c in p.contributions.all().order_by('contributed_at'):
    print(f"  id={c.id} amount={c.amount} date={c.contributed_at}")
    for it in c.items.all():
        print(f"     {it.symbol}: units={it.units} price={it.purchase_price} value={it.value_usd}")

print()
print("=== Выводы средств ===")
for w in p.withdrawals.all():
    print(f"  id={w.id} amount={w.amount} value_after={w.value_after} date={w.withdrawn_at}")

print()
print("=== Свопы (PortfolioSwap) ===")
swaps = PortfolioSwap.objects.filter(portfolio=p).order_by('swapped_at')
print(f"  всего: {swaps.count()}")
for s in swaps:
    print(f"  id={s.id} {s.from_units} {s.from_symbol}@{s.from_price} -> "
          f"{s.to_units} {s.to_symbol}@{s.to_price}  fee_usd={s.fee_usd}  "
          f"date={s.swapped_at}  wallet={s.wallet_id}")

print()
print("=== Переводы между кошельками (WalletTransfer) ===")
trs = WalletTransfer.objects.filter(portfolio=p).order_by('occurred_on')
print(f"  всего: {trs.count()}")
for t in trs:
    print(f"  id={t.id} {t.symbol}: {t.from_units} ({t.from_wallet_id}) "
          f"-> {t.to_units} ({t.to_wallet_id})  fee={t.fee_units}  "
          f"fee_usd={t.fee_usd}  date={t.occurred_on}")

print()
print("=== Ручные корректировки балансов (HoldingAdjustment) ===")
adjs = HoldingAdjustment.objects.filter(holding__wallet__portfolio=p).order_by('occurred_on')
print(f"  всего: {adjs.count()}")
for a in adjs:
    print(f"  id={a.id} {a.holding.symbol}@wallet={a.holding.wallet_id} "
          f"{a.units_before} -> {a.units_after}  Δ={a.delta}  "
          f"value_delta={a.value_delta_usd}  reason={a.reason}  date={a.occurred_on}")

print()
print("=== Активы (PortfolioAsset) ===")
for a in p.assets.all():
    cost = float(a.units or 0) * float(a.initial_price or 0)
    print(f"  {a.symbol}: units={a.units}  initial_price={a.initial_price}  "
          f"cost_basis(units*init)={cost:.2f}  %={a.percentage}")

print()
print("=== Кошельки и текущие холдинги ===")
total_units_by_sym = {}
for w in Wallet.objects.filter(portfolio=p):
    print(f"  Wallet id={w.id} {w.name!r} default={w.is_default}")
    for h in w.holdings.all():
        print(f"     {h.symbol}: units={h.units}")
        total_units_by_sym.setdefault(h.symbol, Decimal('0'))
        total_units_by_sym[h.symbol] += Decimal(str(h.units or 0))

print()
print("=== Сверка: Σ WalletHolding.units по символу ===")
for sym, u in total_units_by_sym.items():
    a = p.assets.filter(symbol=sym).first()
    pa = a.units if a else None
    match = "OK" if pa is not None and abs(float(pa) - float(u)) < 1e-8 else "MISMATCH"
    print(f"  {sym}: Σholdings={u}  PortfolioAsset.units={pa}  {match}")
