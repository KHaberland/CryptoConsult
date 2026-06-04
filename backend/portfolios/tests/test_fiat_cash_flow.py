"""
Тесты подсистемы FiatCashFlow (PLAN11 — A9).

Покрывают:
  * POST/DELETE /api/portfolio/cash-flows/ и PATCH /api/portfolio/<id>/currency/.
  * `PortfolioAnalyzer.get_fiat_pnl(currency)` — все ветки (no_cash_in,
    USD, USD+withdrawal, EUR через FX, fx_stale).
  * Регрессия legacy-метрики `get_current_value()['profit_loss']`:
    она НЕ зависит от записей FiatCashFlow.

Все внешние интеграции мокаются:
  * `portfolios.services.PriceService.get_prices_in_currency` — крипто-цены.
  * `portfolios.services.PriceService.get_prices_with_changes` — для legacy.
  * `advisor.services._fx_rate` — курс USD↔EUR в `get_fiat_pnl`.
  * `portfolios.views._fx_rate` — курс USD↔EUR в CRUD/смене базовой валюты.

PLAN11 явно запрещает изменения существующих моделей
(``Portfolio.initial_amount``, ``PortfolioContribution``,
``PortfolioWithdrawal``, ``Wallet*``) — тесты их не задействуют.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from advisor.services import PortfolioAnalyzer
from portfolios.models import (
    FiatCashFlow,
    Portfolio,
    PortfolioAsset,
)
from portfolios.services import price_cache


def _create_portfolio(
    session_id: str,
    *,
    base_currency: str = Portfolio.CURRENCY_USD,
    initial_amount: Decimal = Decimal('10000.00'),
    manual_usd_eur_rate: Decimal | None = None,
) -> Portfolio:
    """Создать активный портфель без обращений к внешнему API.

    Возвращает портфель без активов — конкретный набор ассетов добавляется
    в тестах через :func:`_add_btc_asset`.
    """
    return Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый портфель',
        initial_amount=initial_amount,
        target_years=3,
        is_active=True,
        base_currency=base_currency,
        manual_usd_eur_rate=manual_usd_eur_rate,
    )


def _add_btc_asset(
    portfolio: Portfolio,
    *,
    units: Decimal = Decimal('1.00000000'),
    initial_price: Decimal = Decimal('10000.00'),
    percentage: Decimal = Decimal('100.00'),
) -> PortfolioAsset:
    """Добавить актив BTC c заданными units/initial_price.

    Дефолты подобраны так, чтобы у legacy-расчёта
    ``get_current_value().profit_loss`` была простая база:
    при ``portfolio.initial_amount=10000``, ``units=1``,
    ``initial_price=10000`` и моковой цене ``20000`` profit_loss = 10000.
    """
    return PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol='BTC',
        name='Bitcoin',
        percentage=percentage,
        initial_price=initial_price,
        units=units,
        is_recommended=True,
    )


class FiatCashFlowTests(TestCase):
    """Все восемь сценариев PLAN11 — A9 в одном TestCase.

    Для каждого теста создаём свежий ``session_id`` + портфель, чтобы
    тесты были независимыми и порядок выполнения не имел значения.
    """

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        # Глобальный in-memory кэш ``price_cache`` живёт между тестами —
        # сбрасываем, чтобы прошлые EUR-через-FX-флаги не поднимали
        # ``fx_stale=True`` в текущем тесте.
        price_cache.clear()

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    # ------------------------------------------------------------------
    # 1) POST cash-flow: fx_rate_to_base проставляется через _fx_rate
    # ------------------------------------------------------------------

    @patch('portfolios.views._portfolio_fx_rate')
    def test_create_fiat_deposit_persists_fx_rate(self, mock_fx):
        """EUR-портфель + депозит в USD: fx_rate_to_base = _fx_rate(USD, EUR)."""
        mock_fx.return_value = (Decimal('0.92'), False)
        portfolio = _create_portfolio(
            self.session_id, base_currency=Portfolio.CURRENCY_EUR
        )

        response = self.client.post(
            '/api/portfolio/cash-flows/',
            {'kind': 'deposit', 'amount': '1000.00', 'currency': 'USD'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.content
        )
        # _fx_rate был вызван с (currency_операции, base_currency_портфеля).
        mock_fx.assert_called_once_with(portfolio, 'USD', 'EUR')
        # FX-курс не «stale» — в ответе явно False.
        self.assertFalse(response.data['fx_stale'])

        flow = FiatCashFlow.objects.get(portfolio=portfolio)
        self.assertEqual(flow.kind, FiatCashFlow.KIND_DEPOSIT)
        self.assertEqual(flow.amount, Decimal('1000.00'))
        self.assertEqual(flow.currency, 'USD')
        # quantize до 6 знаков — модельное поле DecimalField(12,6).
        self.assertEqual(flow.fx_rate_to_base, Decimal('0.920000'))

    # ------------------------------------------------------------------
    # 2) get_fiat_pnl без cash-flow: no_cash_in=True, 0%
    # ------------------------------------------------------------------

    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_get_fiat_pnl_no_cash_in(self, mock_prices):
        """Пустой FiatCashFlow → no_cash_in=True и profit_loss_percent=0."""
        # У портфеля нет активов и нет cash-flow'ов — крипто-цены не нужны,
        # но мок ставим, чтобы случайно не дёрнуть сеть.
        mock_prices.return_value = {}
        portfolio = _create_portfolio(self.session_id)

        result = PortfolioAnalyzer(portfolio).get_fiat_pnl('USD')

        self.assertEqual(result['currency'], 'USD')
        self.assertEqual(result['cash_in_total'], 0.0)
        self.assertEqual(result['cash_out_total'], 0.0)
        self.assertEqual(result['net_cash_in'], 0.0)
        self.assertEqual(result['current_value'], 0.0)
        self.assertEqual(result['profit_loss'], 0.0)
        # Деление на 0 → 0.0 + флаг no_cash_in.
        self.assertEqual(result['profit_loss_percent'], 0.0)
        self.assertTrue(result['no_cash_in'])
        self.assertFalse(result['fx_stale'])

    # ------------------------------------------------------------------
    # 3) get_fiat_pnl: базовый USD-кейс с одним депозитом и одним BTC
    # ------------------------------------------------------------------

    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_get_fiat_pnl_basic(self, mock_prices):
        """USD: 1 BTC @ $30k, депозит $20k → P&L $10k = 50%."""
        mock_prices.return_value = {'BTC': 30000.0}
        portfolio = _create_portfolio(self.session_id)
        _add_btc_asset(portfolio, units=Decimal('1'))
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('20000.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-01-01',
        )

        result = PortfolioAnalyzer(portfolio).get_fiat_pnl('USD')

        self.assertEqual(result['currency'], 'USD')
        self.assertAlmostEqual(result['cash_in_total'], 20000.0, places=2)
        self.assertAlmostEqual(result['cash_out_total'], 0.0, places=2)
        self.assertAlmostEqual(result['net_cash_in'], 20000.0, places=2)
        self.assertAlmostEqual(result['current_value'], 30000.0, places=2)
        self.assertAlmostEqual(result['profit_loss'], 10000.0, places=2)
        self.assertAlmostEqual(result['profit_loss_percent'], 50.0, places=2)
        self.assertFalse(result['no_cash_in'])
        self.assertFalse(result['fx_stale'])

    # ------------------------------------------------------------------
    # 4) get_fiat_pnl с депозитом и выводом: знаменатель — БРУТТО депозитов
    # ------------------------------------------------------------------

    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_get_fiat_pnl_with_withdrawal(self, mock_prices):
        """Депозит 1000 USD, вывод 200 USD, стоимость 1100 USD → 300/1000 = 30%.

        Знаменатель profit_loss_percent — БРУТТО депозитов (как
        в §2.3 PLAN11), а не net_cash_in. Иначе процент завышался бы.
        """
        # При портфеле с одним BTC и 0.011 unit'ом стоимость = 0.011 * 100000 = 1100.
        mock_prices.return_value = {'BTC': 100000.0}
        portfolio = _create_portfolio(self.session_id)
        _add_btc_asset(portfolio, units=Decimal('0.011'))
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('1000.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-01-01',
        )
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_WITHDRAWAL,
            amount=Decimal('200.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-02-01',
        )

        result = PortfolioAnalyzer(portfolio).get_fiat_pnl('USD')

        self.assertAlmostEqual(result['cash_in_total'], 1000.0, places=2)
        self.assertAlmostEqual(result['cash_out_total'], 200.0, places=2)
        self.assertAlmostEqual(result['net_cash_in'], 800.0, places=2)
        self.assertAlmostEqual(result['current_value'], 1100.0, places=2)
        # 1100 − 800 = 300; 300 / 1000 * 100 = 30.
        self.assertAlmostEqual(result['profit_loss'], 300.0, places=2)
        self.assertAlmostEqual(result['profit_loss_percent'], 30.0, places=2)
        self.assertFalse(result['no_cash_in'])

    # ------------------------------------------------------------------
    # 5) get_fiat_pnl: base_currency=EUR + FX-курс USD→EUR + EUR-цены
    # ------------------------------------------------------------------

    @patch('advisor.services._fx_rate')
    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_get_fiat_pnl_eur_uses_fx_and_eur_prices(
        self, mock_prices, mock_fx
    ):
        """EUR-портфель, USD cash-flow 1000 → cash_in_total ≈ 900 EUR.

        FiatCashFlow.fx_rate_to_base уже сохранён как 0.9 (на момент
        создания записи), поэтому get_fiat_pnl сам _fx_rate не вызывает
        для перевода cash-flow в base. Зато crypto-prices приходят сразу
        в EUR через ``get_prices_in_currency(symbols, 'EUR')``.
        """
        mock_fx.return_value = (Decimal('0.9'), False)
        # 1 BTC по 27000 EUR — стоимость портфеля в base/выбранной валюте.
        mock_prices.return_value = {'BTC': 27000.0}

        portfolio = _create_portfolio(
            self.session_id, base_currency=Portfolio.CURRENCY_EUR
        )
        _add_btc_asset(portfolio, units=Decimal('1'))
        # Имитируем сохранённый в момент создания курс USD→EUR=0.9.
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('1000.00'),
            currency='USD',
            fx_rate_to_base=Decimal('0.900000'),
            occurred_on='2024-01-01',
        )

        result = PortfolioAnalyzer(portfolio).get_fiat_pnl('EUR')

        self.assertEqual(result['currency'], 'EUR')
        # cur == base (EUR), поэтому fx_b2c=1 и cash_in = amount_in_base.
        self.assertAlmostEqual(result['cash_in_total'], 900.0, places=2)
        # current_value берём строго из EUR-цен (через get_prices_in_currency).
        self.assertAlmostEqual(result['current_value'], 27000.0, places=2)
        # P&L в EUR: 27000 − 900 = 26100; 26100 / 900 * 100 ≈ 2900%.
        self.assertAlmostEqual(result['profit_loss'], 26100.0, places=2)
        self.assertAlmostEqual(
            result['profit_loss_percent'], 2900.0, places=1
        )
        # Запрошены EUR-цены ровно один раз для известных символов.
        mock_prices.assert_called_with(['BTC'], 'EUR')

    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_get_fiat_pnl_eur_uses_manual_rate_for_usd_value(self, mock_prices):
        """Ручной USD→EUR курс управляет EUR-стоимостью и P&L."""
        mock_prices.return_value = {'BTC': 30000.0}
        portfolio = _create_portfolio(
            self.session_id,
            base_currency=Portfolio.CURRENCY_EUR,
            manual_usd_eur_rate=Decimal('0.800000'),
        )
        _add_btc_asset(portfolio, units=Decimal('1'))
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('1000.00'),
            currency='USD',
            fx_rate_to_base=Decimal('0.800000'),
            occurred_on='2024-01-01',
        )

        result = PortfolioAnalyzer(portfolio).get_fiat_pnl('EUR')

        self.assertAlmostEqual(result['cash_in_total'], 800.0, places=2)
        self.assertAlmostEqual(result['current_value'], 24000.0, places=2)
        self.assertAlmostEqual(result['profit_loss'], 23200.0, places=2)
        self.assertAlmostEqual(result['profit_loss_percent'], 2900.0, places=2)
        mock_prices.assert_called_with(['BTC'], 'USD')

    # ------------------------------------------------------------------
    # 6) PATCH /api/portfolio/<id>/currency/ пересчитывает fx_rate_to_base
    # ------------------------------------------------------------------

    @patch('portfolios.views._portfolio_fx_rate')
    def test_change_base_currency_recalculates_fx(self, mock_fx):
        """Смена USD → EUR пересчитывает fx_rate_to_base у всех cash-flow'ов."""
        mock_fx.return_value = (Decimal('0.9'), False)
        portfolio = _create_portfolio(self.session_id)
        flow = FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('500.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-01-01',
        )

        response = self.client.patch(
            f'/api/portfolio/{portfolio.id}/currency/',
            {'base_currency': 'EUR'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertTrue(response.data['ok'])
        self.assertEqual(response.data['base_currency'], 'EUR')
        self.assertFalse(response.data['fx_stale'])
        # _fx_rate(flow.currency, new_base) — для каждого flow.
        args, _ = mock_fx.call_args
        self.assertEqual(args[1:], ('USD', 'EUR'))

        portfolio.refresh_from_db()
        flow.refresh_from_db()
        self.assertEqual(portfolio.base_currency, 'EUR')
        self.assertEqual(flow.fx_rate_to_base, Decimal('0.900000'))

    def test_patch_manual_rate_recalculates_existing_flows(self):
        """Смена ручного USD→EUR курса пересчитывает существующие cash-flow."""
        portfolio = _create_portfolio(
            self.session_id,
            base_currency=Portfolio.CURRENCY_EUR,
            manual_usd_eur_rate=Decimal('0.900000'),
        )
        flow = FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('500.00'),
            currency='USD',
            fx_rate_to_base=Decimal('0.900000'),
            occurred_on='2024-01-01',
        )

        response = self.client.patch(
            f'/api/portfolio/{portfolio.id}/currency/',
            {'base_currency': 'EUR', 'manual_usd_eur_rate': '0.85'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.data['manual_usd_eur_rate'], 0.85)

        portfolio.refresh_from_db()
        flow.refresh_from_db()
        self.assertEqual(portfolio.manual_usd_eur_rate, Decimal('0.850000'))
        self.assertEqual(flow.fx_rate_to_base, Decimal('0.850000'))

    # ------------------------------------------------------------------
    # 7) DELETE cash-flow уменьшает cash_in_total ровно на удалённую сумму
    # ------------------------------------------------------------------

    @patch('portfolios.services.PriceService.get_prices_in_currency')
    def test_delete_fiat_cash_flow(self, mock_prices):
        """DELETE → cash_in_total падает ровно на сумму удалённого depositа."""
        # Чтобы изолировать эффект удаления — оставляем портфель без активов;
        # тогда current_value=0 и единственный «движущийся» показатель — cash_in.
        mock_prices.return_value = {}
        portfolio = _create_portfolio(self.session_id)
        flow = FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('500.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-01-01',
        )

        analyzer = PortfolioAnalyzer(portfolio)
        before = analyzer.get_fiat_pnl('USD')
        self.assertAlmostEqual(before['cash_in_total'], 500.0, places=2)
        self.assertFalse(before['no_cash_in'])

        response = self.client.delete(
            f'/api/portfolio/cash-flows/{flow.id}/',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            FiatCashFlow.objects.filter(pk=flow.id).exists()
        )

        after = PortfolioAnalyzer(portfolio).get_fiat_pnl('USD')
        # cash_in уменьшился ровно на 500 (то есть стал 0).
        self.assertAlmostEqual(
            before['cash_in_total'] - after['cash_in_total'],
            500.0, places=2,
        )
        self.assertAlmostEqual(after['cash_in_total'], 0.0, places=2)
        self.assertTrue(after['no_cash_in'])

    # ------------------------------------------------------------------
    # 8) Legacy-метрика не зависит от FiatCashFlow
    # ------------------------------------------------------------------

    @patch('portfolios.services.PriceService.get_prices_with_changes')
    def test_legacy_metrics_unchanged(self, mock_changes):
        """``get_current_value()`` НЕ зависит от наличия FiatCashFlow.

        PLAN11 — антискоуп: старый расчёт от ``Portfolio.initial_amount``
        + ``Σ contributions`` остаётся для AI-промптов и onboarding'а.
        Регрессия гарантирует, что новая модель FiatCashFlow не утечёт
        в это вычисление.
        """
        mock_changes.return_value = {
            'BTC': {'price': 20000.0, 'change_24h': 1.5},
        }
        portfolio = _create_portfolio(
            self.session_id, initial_amount=Decimal('10000.00')
        )
        _add_btc_asset(
            portfolio,
            units=Decimal('1'),
            initial_price=Decimal('10000.00'),
        )

        legacy_before = PortfolioAnalyzer(portfolio).get_current_value()
        # 1 BTC @ 20000 vs. initial_amount 10000 → +10000 (+100%).
        self.assertAlmostEqual(
            legacy_before['profit_loss'], 10000.0, places=2
        )
        self.assertAlmostEqual(
            legacy_before['profit_loss_percent'], 100.0, places=2
        )
        self.assertAlmostEqual(
            legacy_before['initial_value'], 10000.0, places=2
        )
        self.assertAlmostEqual(
            legacy_before['current_value'], 20000.0, places=2
        )

        # Создаём cash-flow на сопоставимую сумму — legacy-метрики
        # обязаны остаться прежними.
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('5000.00'),
            currency='USD',
            fx_rate_to_base=Decimal('1.000000'),
            occurred_on='2024-01-01',
        )

        legacy_after = PortfolioAnalyzer(portfolio).get_current_value()
        self.assertAlmostEqual(
            legacy_after['profit_loss'],
            legacy_before['profit_loss'],
            places=2,
        )
        self.assertAlmostEqual(
            legacy_after['profit_loss_percent'],
            legacy_before['profit_loss_percent'],
            places=2,
        )
        self.assertAlmostEqual(
            legacy_after['initial_value'],
            legacy_before['initial_value'],
            places=2,
        )
        self.assertAlmostEqual(
            legacy_after['current_value'],
            legacy_before['current_value'],
            places=2,
        )
