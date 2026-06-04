"""Свежий диагноз портфеля id=27 (real / импорт)."""
import os, sys, django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from portfolios.models import (
    Portfolio, FiatCashFlow,
    Wallet, WalletHolding, WalletTransfer, HoldingAdjustment,
    PortfolioSwap, PortfolioContribution, PortfolioWithdrawal,
)
from portfolios.services import PriceService
from advisor.services import PortfolioAnalyzer


def U(x):
    return f"{float(x or 0):,.2f}"


p = Portfolio.objects.get(pk=27)
print(f"Portfolio #{p.id}: {p.name!r}")
print(f"  initial_amount = {p.initial_amount}")
print(f"  base_currency  = {p.base_currency}")
print(f"  is_imported    = {p.is_imported}")
print(f"  start_date     = {p.start_date}")
print()

# -------- FiatCashFlow --------
flows = list(p.fiat_cash_flows.all().order_by('occurred_on', 'created_at'))
print(f"=== FiatCashFlow ({len(flows)} шт.) ===")
cash_in = Decimal('0')
cash_out = Decimal('0')
for f in flows:
    print(f"  id={f.id}  {f.kind:>10}  {f.amount} {f.currency}  fx={f.fx_rate_to_base}  "
          f"in_base={f.amount_in_base}  date={f.occurred_on}  note={f.note!r}")
    if f.kind == FiatCashFlow.KIND_DEPOSIT:
        cash_in += f.amount_in_base
    else:
        cash_out += f.amount_in_base
print(f"  Σ deposits      = {U(cash_in)} {p.base_currency}")
print(f"  Σ withdrawals   = {U(cash_out)} {p.base_currency}")
print(f"  net_cash_in     = {U(cash_in - cash_out)} {p.base_currency}")
print()

# -------- Старый учёт --------
contribs = list(p.contributions.all().order_by('contributed_at'))
print(f"=== PortfolioContribution ({len(contribs)} шт.) ===")
c_sum = Decimal('0')
for c in contribs:
    print(f"  id={c.id}  amount={c.amount}  date={c.contributed_at}")
    for it in c.items.all():
        print(f"     {it.symbol}: units={it.units}  price={it.purchase_price}  value=${it.value_usd}")
    c_sum += c.amount or Decimal('0')
print(f"  Σ contributions = {U(c_sum)}")
print(f"  initial_amount + Σ contributions = {U((p.initial_amount or 0) + c_sum)}")
print()

# -------- Активы и текущая стоимость --------
assets = list(p.assets.all())
symbols = [a.symbol for a in assets]
prices_usd = PriceService().get_prices(symbols)
print(f"=== Активы и текущая стоимость (units × spot, USD) ===")
total_now = 0.0
for a in assets:
    cur = float(prices_usd.get(a.symbol) or 0)
    u = float(a.units or 0)
    print(f"  {a.symbol:>5}  units={u:.8f}  init_price={a.initial_price}  cur_price=${cur:,.2f}  "
          f"value=${u*cur:,.2f}  cost_basis(units*init)=${u*float(a.initial_price or 0):,.2f}  pct={a.percentage}%")
    total_now += u * cur
print(f"  Σ current_value (units × spot)  = ${total_now:,.2f}")
print()

# -------- Метрики analyzer --------
print(f"=== PortfolioAnalyzer ===")
val = PortfolioAnalyzer(p).get_current_value()
print(f"  get_current_value():")
print(f"     initial_value  = ${val['initial_value']:,.2f}")
print(f"     current_value  = ${val['current_value']:,.2f}")
print(f"     profit_loss    = ${val['profit_loss']:+,.2f}")
print(f"     profit_loss_%  = {val['profit_loss_percent']:+.2f}%")
print()

pnl_usd = PortfolioAnalyzer(p).get_fiat_pnl('USD')
print(f"  get_fiat_pnl('USD'):")
for k, v in pnl_usd.items():
    print(f"     {k:>22} = {v}")
print()

# -------- Все корректировки и переводы --------
adjs = HoldingAdjustment.objects.filter(holding__wallet__portfolio=p).order_by('occurred_on')
print(f"=== HoldingAdjustment ({adjs.count()} шт.) ===")
total_value_delta = Decimal('0')
for a in adjs:
    print(f"  {a.occurred_on}  {a.holding.symbol:>5}@w{a.holding.wallet_id}  "
          f"{a.units_before} → {a.units_after}  Δ={a.delta:+}  value_Δ=${a.value_delta_usd:+}  "
          f"reason={a.reason}  note={a.note!r}")
    total_value_delta += a.value_delta_usd or Decimal('0')
print(f"  Σ value_delta_usd = ${total_value_delta:+}")
print()

trs = WalletTransfer.objects.filter(portfolio=p).order_by('occurred_on')
print(f"=== WalletTransfer ({trs.count()} шт.) ===")
for t in trs:
    print(f"  {t.occurred_on}  {t.symbol}: {t.from_units} (w{t.from_wallet_id}) → {t.to_units} (w{t.to_wallet_id})  "
          f"fee={t.fee_units} ({t.fee_usd}$)")
print()

swaps = PortfolioSwap.objects.filter(portfolio=p).order_by('swapped_at')
print(f"=== PortfolioSwap ({swaps.count()} шт.) ===")
for s in swaps:
    print(f"  {s.swapped_at}  {s.from_units} {s.from_symbol}@${s.from_price} → "
          f"{s.to_units} {s.to_symbol}@${s.to_price}  fee=${s.fee_usd}  wallet={s.wallet_id}")
print()

# -------- Кошельки --------
print(f"=== Кошельки ===")
total_units = {}
for w in Wallet.objects.filter(portfolio=p):
    print(f"  Wallet #{w.id}  {w.name!r}  default={w.is_default}")
    for h in w.holdings.all():
        print(f"     {h.symbol}: units={h.units}")
        total_units.setdefault(h.symbol, Decimal('0'))
        total_units[h.symbol] += Decimal(str(h.units or 0))
print()
print(f"=== Σ WalletHolding.units vs PortfolioAsset.units ===")
for sym, u in total_units.items():
    a = p.assets.filter(symbol=sym).first()
    pa = a.units if a else None
    ok = "OK" if pa is not None and abs(float(pa) - float(u)) < 1e-8 else "MISMATCH"
    print(f"  {sym}: Σholdings={u}  PortfolioAsset.units={pa}  {ok}")
