"""
Тесты перевода активов между кошельками
(POST /api/portfolio/wallets/transfer/).

PLAN06 — ЭТАП 7, агент T2.

Покрываем:
- обычный перевод (без комиссии);
- перевод с комиссией (fee_units = from_units − to_units);
- недостаточный баланс на from_wallet → 400;
- to_units > from_units → 400 (валидация сериализатора);
- перевод в тот же кошелёк → 400 (валидация сериализатора);
- отрицательные / нулевые units → 400;
- несуществующий кошелёк / чужой портфель → 400/404;
- инвариант PortfolioAsset.units = Σ WalletHolding.units после перевода;
- fee_usd считается по текущей цене актива.
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
    WalletTransfer,
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


def _create_portfolio_with_two_wallets(session_id):
    """Готовит портфель с двумя кошельками и одним активом BTC.

    initial_amount = 5000$
    BTC: 0.05 units (стоимость 5000$ при цене 100000)

    Все units лежат на default-кошельке ("Общий кошелёк"), второй
    кошелёк ("Холодный") изначально пустой.
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
    return portfolio, main_wallet, cold_wallet


def _aggregate_units(portfolio: Portfolio, symbol: str) -> Decimal:
    total = Decimal('0')
    for h in WalletHolding.objects.filter(wallet__portfolio=portfolio, symbol=symbol):
        total += Decimal(h.units)
    return total


class WalletTransferTests(TestCase):
    """POST /api/portfolio/wallets/transfer/."""

    URL = '/api/portfolio/wallets/transfer/'

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    # ------------------------------------------------------------------
    # Базовые сценарии
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_simple_transfer_no_fee(self, mock_class):
        """Обычный перевод (to_units == from_units), комиссии нет."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.02000000',
                'to_units': '0.02000000',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        data = response.json()
        self.assertTrue(data['success'])
        t = data['transfer']
        self.assertEqual(Decimal(t['from_units']), Decimal('0.02'))
        self.assertEqual(Decimal(t['to_units']), Decimal('0.02'))
        self.assertEqual(Decimal(t['fee_units']), Decimal('0'))
        self.assertEqual(Decimal(t['fee_usd']), Decimal('0.00'))

        # balances
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        h_cold = WalletHolding.objects.get(wallet=cold_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.03'))
        self.assertEqual(h_cold.units, Decimal('0.02'))

        # PortfolioAsset.units не изменился (комиссии нет — units просто переехали)
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0.05'))
        self.assertEqual(asset.units, _aggregate_units(portfolio, 'BTC'))

        # Запись WalletTransfer создана
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 1)
        wt = WalletTransfer.objects.get(portfolio=portfolio)
        self.assertEqual(wt.from_wallet_id, main_w.id)
        self.assertEqual(wt.to_wallet_id, cold_w.id)
        self.assertEqual(wt.symbol, 'BTC')
        self.assertEqual(wt.fee_units, Decimal('0'))

    @patch('portfolios.views.PriceService')
    def test_transfer_with_fee(self, mock_class):
        """Перевод с комиссией (to_units < from_units): units «сгорают»."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.02000000',
                'to_units': '0.01950000',
                'note': 'перевод на холодный кошелёк',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        t = response.json()['transfer']
        # fee_units = 0.02 - 0.0195 = 0.0005
        self.assertEqual(Decimal(t['fee_units']), Decimal('0.0005'))
        # fee_usd = 0.0005 * 100000 = 50.00
        self.assertEqual(Decimal(t['fee_usd']), Decimal('50.00'))
        self.assertEqual(t['note'], 'перевод на холодный кошелёк')

        # balances: списали 0.02 с main, зачислили 0.0195 на cold
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        h_cold = WalletHolding.objects.get(wallet=cold_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.03'))
        self.assertEqual(h_cold.units, Decimal('0.0195'))

        # PortfolioAsset.units = Σ holdings = 0.03 + 0.0195 = 0.0495
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0.0495'))
        self.assertEqual(asset.units, _aggregate_units(portfolio, 'BTC'))

    @patch('portfolios.views.PriceService')
    def test_transfer_creates_holding_on_target_wallet(self, mock_class):
        """Если на to_wallet ещё нет holding по symbol — он создаётся."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)
        self.assertFalse(
            WalletHolding.objects.filter(wallet=cold_w, symbol='BTC').exists()
        )

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.01',
                'to_units': '0.01',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        h_cold = WalletHolding.objects.get(wallet=cold_w, symbol='BTC')
        self.assertEqual(h_cold.units, Decimal('0.01'))

    # ------------------------------------------------------------------
    # Валидация
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_insufficient_balance(self, mock_class):
        """Списать больше, чем есть на from_wallet → 400, изменений нет."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '1.00000000',  # есть только 0.05
                'to_units': '1.00000000',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

        # balances не изменились
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.05'))
        # на cold так и нет holding
        self.assertFalse(
            WalletHolding.objects.filter(wallet=cold_w, symbol='BTC').exists()
        )

        # Запись WalletTransfer не создана (atomic откатил всё)
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)

        # PortfolioAsset.units не пострадал
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, Decimal('0.05'))

    @patch('portfolios.views.PriceService')
    def test_to_units_greater_than_from_units(self, mock_class):
        """to_units > from_units → 400 (валидация сериализатора)."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.01000000',
                'to_units': '0.02000000',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        # никаких записей и изменений
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.05'))
        self.assertFalse(
            WalletHolding.objects.filter(wallet=cold_w, symbol='BTC').exists()
        )

    @patch('portfolios.views.PriceService')
    def test_same_wallet_rejected(self, mock_class):
        """Перевод в тот же кошелёк → 400 (валидация сериализатора)."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, _cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': main_w.id,
                'symbol': 'BTC',
                'from_units': '0.01000000',
                'to_units': '0.01000000',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.05'))

    @patch('portfolios.views.PriceService')
    def test_zero_units_rejected(self, mock_class):
        """Нулевые units → 400 (units > 0)."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0',
                'to_units': '0',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)

    @patch('portfolios.views.PriceService')
    def test_negative_units_rejected(self, mock_class):
        """Отрицательные units → 400."""
        _setup_price_service_mock(mock_class)
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '-0.01',
                'to_units': '-0.01',
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)

    # ------------------------------------------------------------------
    # 404 / чужие портфели
    # ------------------------------------------------------------------

    def test_no_active_portfolio(self):
        """Нет активного портфеля → 404."""
        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': 1,
                'to_wallet_id': 2,
                'symbol': 'BTC',
                'from_units': '0.01',
                'to_units': '0.01',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    @patch('portfolios.views.PriceService')
    def test_unknown_from_wallet(self, mock_class):
        """from_wallet_id, не принадлежащий активному портфелю → 400."""
        _setup_price_service_mock(mock_class)
        _portfolio, _main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': 999999,
                'to_wallet_id': cold_w.id,
                'symbol': 'BTC',
                'from_units': '0.01',
                'to_units': '0.01',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(WalletTransfer.objects.count(), 0)

    @patch('portfolios.views.PriceService')
    def test_foreign_wallet_not_accessible(self, mock_class):
        """Кошелёк другого портфеля недоступен текущей сессии → 400."""
        _setup_price_service_mock(mock_class)
        _portfolio, main_w, _cold_w = _create_portfolio_with_two_wallets(self.session_id)

        # Чужой портфель + кошелёк
        other_portfolio = Portfolio.objects.create(
            session_id=str(uuid.uuid4()),
            name='Чужой',
            initial_amount=Decimal('1000'),
            target_years=3,
            is_active=True,
        )
        foreign_wallet = Wallet.objects.create(
            portfolio=other_portfolio,
            name='Чужой холодный',
            type=Wallet.TYPE_COLD,
            is_default=False,
        )

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': foreign_wallet.id,
                'symbol': 'BTC',
                'from_units': '0.01',
                'to_units': '0.01',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        # Никаких изменений в исходных балансах
        h_main = WalletHolding.objects.get(wallet=main_w, symbol='BTC')
        self.assertEqual(h_main.units, Decimal('0.05'))
        self.assertEqual(WalletTransfer.objects.count(), 0)

    def test_unsupported_symbol_rejected(self):
        """Неподдерживаемый символ → 400 (валидация symbol через PriceService)."""
        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
            {
                'from_wallet_id': main_w.id,
                'to_wallet_id': cold_w.id,
                'symbol': 'NOPE',
                'from_units': '0.01',
                'to_units': '0.01',
            },
            format='json',
            **self._headers(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        self.assertEqual(WalletTransfer.objects.filter(portfolio=portfolio).count(), 0)

    # ------------------------------------------------------------------
    # Цена недоступна — fee_usd должен быть 0, а не упасть
    # ------------------------------------------------------------------

    @patch('portfolios.views.PriceService')
    def test_fee_usd_zero_when_price_missing(self, mock_class):
        """Если PriceService.get_prices не вернул цену — fee_usd = 0, перевод проходит."""
        mock_service = MagicMock()
        mock_service.get_prices.return_value = {}
        mock_class.return_value = mock_service

        portfolio, main_w, cold_w = _create_portfolio_with_two_wallets(self.session_id)

        response = self.client.post(
            self.URL,
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
        t = response.json()['transfer']
        self.assertEqual(Decimal(t['fee_units']), Decimal('0.0005'))
        self.assertEqual(Decimal(t['fee_usd']), Decimal('0.00'))

        # инвариант
        asset = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertEqual(asset.units, _aggregate_units(portfolio, 'BTC'))
