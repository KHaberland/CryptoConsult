"""
Тест инварианта мультикошельковой модели.

PLAN06-realization.md — ЭТАП 7, агент T4.

Инвариант:
    PortfolioAsset.units == Σ WalletHolding.units
    по всем кошелькам портфеля для данного symbol.

Проверяем, что инвариант сохраняется ПОСЛЕ КАЖДОЙ из четырёх операций
(contribute / swap / transfer / adjustment) — как по отдельности
(каждая операция в чистом портфеле), так и в сквозном сценарии,
когда все четыре операции выполняются последовательно над одним
портфелем.
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
    Wallet,
    WalletHolding,
)


MOCK_PRICES = {
    'BTC': 100000.0,
    'ETH': 3500.0,
    'SOL': 250.0,
    'USDT': 1.0,
    'USDC': 1.0,
    'XRP': 3.0,
    'BNB': 700.0,
    'ADA': 1.0,
    'DOGE': 0.4,
    'DOT': 8.0,
    'LINK': 25.0,
    'TRX': 0.25,
}

MOCK_TOP10 = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'DOT']


def _setup_price_service_mock(mock_class):
    mock_service = MagicMock()
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_service.get_top10_recommended_symbols.return_value = MOCK_TOP10
    mock_service.get_top10_recommended_assets.return_value = [
        {'symbol': s, 'name': s, 'current_price': MOCK_PRICES.get(s, 0), 'market_cap': 0}
        for s in MOCK_TOP10
    ]
    mock_class.return_value = mock_service
    return mock_service


def _aggregate_units(portfolio: Portfolio, symbol: str) -> Decimal:
    """Σ WalletHolding.units по всем кошелькам портфеля для symbol."""
    total = Decimal('0')
    for h in WalletHolding.objects.filter(
        wallet__portfolio=portfolio, symbol=symbol
    ):
        total += Decimal(h.units)
    return total


def _create_portfolio_with_two_wallets(session_id):
    """Портфель: 0.05 BTC + 1000 USDT, два кошелька (default + холодный).

    На default-кошельке лежат все units (как сразу после backfill-миграции).
    Второй кошелёк изначально пустой.
    """
    portfolio = Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый',
        initial_amount=Decimal('6000'),
        target_years=5,
        is_active=True,
    )
    PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol='BTC',
        name='Bitcoin',
        percentage=Decimal('80'),
        initial_price=Decimal('100000'),
        units=Decimal('0.05'),
        is_recommended=True,
    )
    PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol='USDT',
        name='Tether',
        percentage=Decimal('20'),
        initial_price=Decimal('1'),
        units=Decimal('1000'),
        is_recommended=False,
    )
    main_wallet = Wallet.objects.create(
        portfolio=portfolio,
        name='Общий кошелёк',
        type=Wallet.TYPE_OTHER,
        is_default=True,
    )
    cold_wallet = Wallet.objects.create(
        portfolio=portfolio,
        name='Холодный',
        type=Wallet.TYPE_COLD,
        is_default=False,
    )
    WalletHolding.objects.create(
        wallet=main_wallet, symbol='BTC', units=Decimal('0.05'),
    )
    WalletHolding.objects.create(
        wallet=main_wallet, symbol='USDT', units=Decimal('1000'),
    )
    return portfolio, main_wallet, cold_wallet


class InvariantTests(TestCase):
    """PortfolioAsset.units == Σ WalletHolding.units после каждой операции."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _assert_invariant(self, portfolio: Portfolio, after: str):
        """Сравнить PortfolioAsset.units с Σ WalletHolding.units по каждому активу."""
        portfolio.refresh_from_db()
        for asset in portfolio.assets.all():
            asset.refresh_from_db()
            aggregate = _aggregate_units(portfolio, asset.symbol)
            self.assertEqual(
                Decimal(asset.units), aggregate,
                msg=(
                    f'инвариант нарушен для {asset.symbol} после "{after}": '
                    f'PortfolioAsset.units={asset.units}, '
                    f'Σ WalletHolding.units={aggregate}'
                ),
            )

    # ------------------------------------------------------------------
    # Каждая операция по отдельности (на свежем портфеле)
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_invariant_after_contribute(self, mock_class):
        """Инвариант сохраняется после POST /contribute/."""
        _setup_price_service_mock(mock_class)
        portfolio, _, _ = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            '/api/portfolio/contribute/',
            {'items': [
                {'symbol': 'BTC', 'units': 0.01, 'purchase_price': 95000},
                {'symbol': 'USDT', 'units': 250},
            ]},
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        self._assert_invariant(portfolio, 'contribute')
        # Балансы выросли на величину пополнения.
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        usdt = PortfolioAsset.objects.get(portfolio=portfolio, symbol='USDT')
        self.assertEqual(btc.units, Decimal('0.06'))
        self.assertEqual(usdt.units, Decimal('1250'))

    @patch('portfolios.views.PriceService')
    def test_invariant_after_swap(self, mock_class):
        """Инвариант сохраняется после POST /swap/."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, _ = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            '/api/portfolio/swap/',
            {
                'from_symbol': 'USDT',
                'from_units': 200,
                'to_symbol': 'BTC',
                'to_units': 0.002,
                'wallet_id': main_w.id,
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        self._assert_invariant(portfolio, 'swap')
        # Σ USDT уменьшилась, Σ BTC выросла; общая сумма Σ совпадает с PortfolioAsset.
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        usdt = PortfolioAsset.objects.get(portfolio=portfolio, symbol='USDT')
        self.assertEqual(btc.units, Decimal('0.052'))
        self.assertEqual(usdt.units, Decimal('800'))

    @patch('portfolios.views.PriceService')
    def test_invariant_after_transfer(self, mock_class):
        """Инвариант сохраняется после POST /wallets/transfer/.

        Перевод с комиссией: Σ holdings уменьшается на fee_units,
        PortfolioAsset.units должен пересчитаться ровно на ту же дельту.
        """
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            '/api/portfolio/wallets/transfer/',
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.02000000',
                'to_units': '0.01950000',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        self._assert_invariant(portfolio, 'transfer')
        # На обоих кошельках теперь есть BTC, сумма = 0.0495 (минус fee 0.0005).
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(btc.units, Decimal('0.0495'))
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        h_cold = WalletHolding.objects.get(wallet=cold_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.03'))
        self.assertEqual(h_cold.units, Decimal('0.0195'))

    @patch('portfolios.views.PriceService')
    def test_invariant_after_adjustment(self, mock_class):
        """Инвариант сохраняется после POST /wallets/<id>/holdings/<symbol>/adjust/."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, _ = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            f'/api/portfolio/wallets/{main_w.id}/holdings/BTC/adjust/',
            {
                'units_after': '0.04950000',
                'reason': 'network_fee',
                'note': 'комиссия сети',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        self._assert_invariant(portfolio, 'adjustment')
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(btc.units, Decimal('0.0495'))

    # ------------------------------------------------------------------
    # Сквозной сценарий: все четыре операции на одном портфеле
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_invariant_holds_through_full_sequence(self, mock_class):
        """contribute → swap → transfer → adjustment: инвариант после каждого шага."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        # Базовое состояние тоже должно быть консистентно.
        self._assert_invariant(portfolio, 'setup')

        # 1) contribute: +0.01 BTC, +500 USDT на default-кошелёк.
        r = self.client.post(
            '/api/portfolio/contribute/',
            {'items': [
                {'symbol': 'BTC', 'units': 0.01, 'purchase_price': 95000},
                {'symbol': 'USDT', 'units': 500},
            ]},
            format='json',
            **self._headers(),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self._assert_invariant(portfolio, 'contribute')

        # 2) swap: 300 USDT → 0.003 BTC на default-кошельке.
        r = self.client.post(
            '/api/portfolio/swap/',
            {
                'from_symbol': 'USDT',
                'from_units': 300,
                'to_symbol': 'BTC',
                'to_units': 0.003,
                'wallet_id': main_w.id,
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self._assert_invariant(portfolio, 'swap')

        # 3) transfer: 0.02 BTC с main → cold с комиссией (fee_units = 0.0005).
        r = self.client.post(
            '/api/portfolio/wallets/transfer/',
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.02000000',
                'to_units': '0.01950000',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self._assert_invariant(portfolio, 'transfer')

        # 4) adjustment: уменьшим BTC на cold-кошельке ещё на 0.0001 (network_fee).
        cold_btc = WalletHolding.objects.get(wallet=cold_w, symbol='BTC')
        new_units = (Decimal(cold_btc.units) - Decimal('0.0001')).quantize(
            Decimal('0.00000001')
        )
        r = self.client.post(
            f'/api/portfolio/wallets/{cold_w.id}/holdings/BTC/adjust/',
            {
                'units_after': str(new_units),
                'reason': 'network_fee',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.content)
        self._assert_invariant(portfolio, 'adjustment')

        # Итоговое состояние: BTC = 0.05 + 0.01 (contrib) + 0.003 (swap) - 0.0005 (transfer fee) - 0.0001 (adjust)
        # = 0.0624; USDT = 1000 + 500 (contrib) - 300 (swap) = 1200.
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        usdt = PortfolioAsset.objects.get(portfolio=portfolio, symbol='USDT')
        self.assertEqual(btc.units, Decimal('0.0624'))
        self.assertEqual(usdt.units, Decimal('1200'))
