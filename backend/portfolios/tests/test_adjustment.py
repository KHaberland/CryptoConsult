"""
Тесты ручной коррекции баланса WalletHolding
(POST /api/portfolio/wallets/<wallet_id>/holdings/<symbol>/adjust/).

Проверяем:
- уменьшение баланса (network_fee, exchange_fee, …);
- увеличение баланса;
- корректировку в 0;
- запрет отрицательных значений;
- инвариант PortfolioAsset.units == Σ WalletHolding.units;
- что Net Invested не меняется (initial_amount + Σ contributions − Σ withdrawals);
- 404 на несуществующий кошелёк / неактивный портфель.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from portfolios.models import (
    Portfolio,
    PortfolioAsset,
    PortfolioContribution,
    PortfolioWithdrawal,
    Wallet,
    WalletHolding,
    HoldingAdjustment,
)


MOCK_PRICES = {
    'BTC': 100000.0,
    'ETH': 3500.0,
    'USDT': 1.0,
}


def _setup_price_service_mock(mock_class):
    mock_service = MagicMock()
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_class.return_value = mock_service
    return mock_service


def _create_portfolio_with_wallet(session_id):
    """Готовит портфель с одним кошельком и одной позицией BTC.

    initial_amount = 5000$
    BTC: 0.05 units (стоимость 5000$ при цене 100000)
    """
    portfolio = Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый',
        initial_amount=Decimal('5000'),
        target_years=5,
        is_active=True,
    )
    PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol='BTC',
        name='Bitcoin',
        percentage=Decimal('100'),
        initial_price=Decimal('100000'),
        units=Decimal('0.05'),
        is_recommended=True,
    )
    wallet = Wallet.objects.create(
        portfolio=portfolio,
        name='Общий кошелёк',
        type=Wallet.TYPE_OTHER,
        is_default=True,
    )
    WalletHolding.objects.create(
        wallet=wallet,
        symbol='BTC',
        units=Decimal('0.05'),
    )
    return portfolio, wallet


def _net_invested(portfolio: Portfolio) -> Decimal:
    """Сумма «Net Invested» — то, что не должно меняться от adjustment."""
    contrib = sum(
        (c.amount for c in PortfolioContribution.objects.filter(portfolio=portfolio)),
        Decimal('0'),
    )
    withd = sum(
        (w.amount for w in PortfolioWithdrawal.objects.filter(portfolio=portfolio)),
        Decimal('0'),
    )
    return Decimal(portfolio.initial_amount) + Decimal(contrib) - Decimal(withd)


def _aggregate_units(portfolio: Portfolio, symbol: str) -> Decimal:
    total = Decimal('0')
    for h in WalletHolding.objects.filter(wallet__portfolio=portfolio, symbol=symbol):
        total += Decimal(h.units)
    return total


class HoldingAdjustTests(TestCase):
    """POST /api/portfolio/wallets/<wallet_id>/holdings/<symbol>/adjust/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _url(self, wallet_id, symbol):
        return f'/api/portfolio/wallets/{wallet_id}/holdings/{symbol}/adjust/'

    # ------------------------------------------------------------------
    # Базовые сценарии
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_decrease_balance_network_fee(self, mock_class):
        """Уменьшение баланса (комиссия сети)."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_wallet(self.session_id)
        net_before = _net_invested(portfolio)

        response = self.client.post(
            self._url(wallet.id, 'BTC'),
            {
                'units_after': '0.04950000',
                'reason': 'network_fee',
                'note': 'комиссия сети',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        data = response.json()
        adj = data['adjustment']
        self.assertEqual(Decimal(adj['units_before']), Decimal('0.05'))
        self.assertEqual(Decimal(adj['units_after']), Decimal('0.0495'))
        self.assertEqual(Decimal(adj['delta']), Decimal('-0.0005'))
        # value_delta_usd ≈ -0.0005 * 100000 = -50.00
        self.assertEqual(Decimal(adj['value_delta_usd']), Decimal('-50.00'))
        self.assertEqual(adj['reason'], 'network_fee')

        # Holding обновлён
        holding = WalletHolding.objects.get(wallet=wallet, symbol='BTC')
        self.assertEqual(holding.units, Decimal('0.0495'))

        # PortfolioAsset.units пересчитан = Σ holdings
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0.0495'))
        self.assertEqual(asset.units, _aggregate_units(portfolio, 'BTC'))

        # Запись HoldingAdjustment создана
        self.assertEqual(HoldingAdjustment.objects.filter(holding=holding).count(), 1)

        # Net Invested не изменился
        self.assertEqual(_net_invested(portfolio), net_before)

    @patch('portfolios.views.PriceService')
    def test_increase_balance(self, mock_class):
        """Увеличение баланса (например, найдена забытая монета)."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_wallet(self.session_id)
        net_before = _net_invested(portfolio)

        response = self.client.post(
            self._url(wallet.id, 'BTC'),
            {'units_after': '0.06000000', 'reason': 'reconciliation'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        data = response.json()
        self.assertEqual(Decimal(data['adjustment']['delta']), Decimal('0.01'))
        # value_delta_usd ≈ +0.01 * 100000 = +1000.00
        self.assertEqual(Decimal(data['adjustment']['value_delta_usd']), Decimal('1000.00'))

        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0.06'))
        self.assertEqual(_net_invested(portfolio), net_before)

    @patch('portfolios.views.PriceService')
    def test_adjust_to_zero(self, mock_class):
        """Корректировка в ноль допустима (вся позиция списана)."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_wallet(self.session_id)
        net_before = _net_invested(portfolio)

        response = self.client.post(
            self._url(wallet.id, 'BTC'),
            {'units_after': '0', 'reason': 'input_error'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        holding = WalletHolding.objects.get(wallet=wallet, symbol='BTC')
        self.assertEqual(holding.units, Decimal('0'))
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0'))
        self.assertEqual(_net_invested(portfolio), net_before)

    # ------------------------------------------------------------------
    # Валидация
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_negative_units_rejected(self, mock_class):
        """Отрицательное значение units_after → 400."""
        _setup_price_service_mock(mock_class)
        _, wallet = _create_portfolio_with_wallet(self.session_id)

        response = self.client.post(
            self._url(wallet.id, 'BTC'),
            {'units_after': '-0.01'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        # запись не создана
        self.assertEqual(HoldingAdjustment.objects.count(), 0)
        # holding не изменился
        holding = WalletHolding.objects.get(wallet=wallet, symbol='BTC')
        self.assertEqual(holding.units, Decimal('0.05'))

    @patch('portfolios.views.PriceService')
    def test_no_change_rejected(self, mock_class):
        """Если новое значение совпадает с текущим — 400 (нечего корректировать)."""
        _setup_price_service_mock(mock_class)
        _, wallet = _create_portfolio_with_wallet(self.session_id)

        response = self.client.post(
            self._url(wallet.id, 'BTC'),
            {'units_after': '0.05'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(HoldingAdjustment.objects.count(), 0)

    def test_wallet_not_found(self):
        """Несуществующий wallet_id → 404."""
        _create_portfolio_with_wallet(self.session_id)

        response = self.client.post(
            self._url(999999, 'BTC'),
            {'units_after': '0.04'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    def test_no_active_portfolio(self):
        """Нет активного портфеля → 404."""
        # без портфеля
        response = self.client.post(
            self._url(1, 'BTC'),
            {'units_after': '0.04'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    def test_unsupported_symbol_rejected(self):
        """Неподдерживаемый символ → 400 (используем настоящий PriceService.is_symbol_supported)."""
        _, wallet = _create_portfolio_with_wallet(self.session_id)

        response = self.client.post(
            self._url(wallet.id, 'NOPE'),
            {'units_after': '0.04'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    # ------------------------------------------------------------------
    # Инвариант
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_invariant_two_wallets(self, mock_class):
        """Инвариант сохраняется при наличии нескольких кошельков с одним символом."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet_main = _create_portfolio_with_wallet(self.session_id)

        # второй кошелёк с тем же активом
        cold = Wallet.objects.create(
            portfolio=portfolio,
            name='Холодный',
            type=Wallet.TYPE_COLD,
            is_default=False,
        )
        WalletHolding.objects.create(
            wallet=cold,
            symbol='BTC',
            units=Decimal('0.10'),
        )
        # обновим агрегат вручную (имитируем состояние «после миграции»)
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        asset.units = Decimal('0.15')
        asset.save(update_fields=['units'])

        # корректируем только cold-кошелёк
        response = self.client.post(
            self._url(cold.id, 'BTC'),
            {'units_after': '0.09', 'reason': 'network_fee'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        # main-кошелёк не тронут
        h_main = WalletHolding.objects.get(wallet=wallet_main, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.05'))
        # cold-кошелёк обновился
        h_cold = WalletHolding.objects.get(wallet=cold, symbol='BTC')
        self.assertEqual(h_cold.units, Decimal('0.09'))

        # PortfolioAsset = сумма
        asset.refresh_from_db()
        self.assertEqual(asset.units, Decimal('0.14'))
        self.assertEqual(asset.units, _aggregate_units(portfolio, 'BTC'))
