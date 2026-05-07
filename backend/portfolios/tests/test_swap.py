"""
Тесты обмена активов внутри портфеля
(GET /api/portfolio/swap/quote/, POST /api/portfolio/swap/).
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
    PortfolioSwap,
    PortfolioContribution,
    PortfolioWithdrawal,
    Wallet,
    WalletHolding,
)
from portfolios.services import WalletLedger
from users.models import InvestorProfile


MOCK_PRICES = {
    'BTC': 100000.0,
    'ETH': 3500.0,
    'BNB': 700.0,
    'SOL': 250.0,
    'USDT': 1.0,
    'USDC': 1.0,
    'XRP': 3.0,
    'ADA': 1.0,
    'DOGE': 0.4,
    'DOT': 8.0,
    'LINK': 25.0,
}

MOCK_TOP10 = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'DOT']


def _setup_price_service_mock(mock_class):
    mock_service = MagicMock()
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_service.get_top10_recommended_symbols.return_value = MOCK_TOP10
    mock_class.return_value = mock_service
    return mock_service


def _create_portfolio_with_btc_usdt(session_id):
    """Стандартный портфель: 0.05 BTC + 1000 USDT."""
    portfolio = Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый портфель',
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
    return portfolio


class SwapQuoteTests(TestCase):
    """GET /api/portfolio/swap/quote/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/swap/quote/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_swap_quote_basic(self, mock_class):
        """Котировка USDT → BTC: расчёт корректен."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.get(
            self.url,
            {
                'from_symbol': 'USDT',
                'to_symbol': 'BTC',
                'from_units': 100,
            },
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = response.json()
        self.assertEqual(data['from_symbol'], 'USDT')
        self.assertEqual(data['to_symbol'], 'BTC')
        self.assertAlmostEqual(data['from_price'], 1.0, places=4)
        self.assertAlmostEqual(data['to_price'], 100000.0, places=2)
        # 100 USDT → 100/100000 = 0.001 BTC
        self.assertAlmostEqual(data['to_units_expected'], 0.001, places=6)
        self.assertAlmostEqual(data['value_usd'], 100.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_swap_quote_insufficient_units(self, mock_class):
        """Запрос больше, чем доступно → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.get(
            self.url,
            {
                'from_symbol': 'USDT',
                'to_symbol': 'BTC',
                'from_units': 100000,  # больше 1000 USDT
            },
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SwapExecuteTests(TestCase):
    """POST /api/portfolio/swap/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/swap/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_swap_execute_stable_to_btc(self, mock_class):
        """USDT → BTC: списание корректное, начисление, доли пересчитаны, initial_amount не меняется."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)
        initial_amount_before = float(portfolio.initial_amount)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 500,
                'to_symbol': 'BTC',
                'to_units': 0.005,  # ровно по рынку
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        portfolio.refresh_from_db()
        # initial_amount не изменился
        self.assertAlmostEqual(float(portfolio.initial_amount), initial_amount_before, places=2)

        usdt = portfolio.assets.get(symbol='USDT')
        btc = portfolio.assets.get(symbol='BTC')
        # USDT: 1000 - 500 = 500
        self.assertAlmostEqual(float(usdt.units), 500.0, places=4)
        # BTC: 0.05 + 0.005 = 0.055
        self.assertAlmostEqual(float(btc.units), 0.055, places=6)

        # Записан PortfolioSwap
        swaps = PortfolioSwap.objects.filter(portfolio=portfolio)
        self.assertEqual(swaps.count(), 1)
        swap = swaps.first()
        self.assertEqual(swap.from_symbol, 'USDT')
        self.assertEqual(swap.to_symbol, 'BTC')
        # При совпадении с расчётом fee_usd ≈ 0
        self.assertAlmostEqual(float(swap.fee_usd), 0.0, places=2)

        # PortfolioContribution / Withdrawal не созданы
        self.assertEqual(PortfolioContribution.objects.filter(portfolio=portfolio).count(), 0)
        self.assertEqual(PortfolioWithdrawal.objects.filter(portfolio=portfolio).count(), 0)

        # Σ percentage ≈ 100
        total_pct = sum(float(a.percentage) for a in portfolio.assets.all())
        self.assertAlmostEqual(total_pct, 100.0, places=1)

    @patch('portfolios.views.PriceService')
    def test_swap_with_manual_correction_positive_fee(self, mock_class):
        """Ручная коррекция: пользователь получает меньше, чем ожидаемо → fee_usd > 0."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)

        # 100 USDT по рынку = 0.001 BTC, но пользователь корректирует на 0.00095
        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,
                'to_symbol': 'BTC',
                'to_units': 0.00095,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        swap = PortfolioSwap.objects.get(portfolio=portfolio)
        # fee = (0.001 - 0.00095) * 100000 = 5.0
        self.assertGreater(float(swap.fee_usd), 0)
        self.assertAlmostEqual(float(swap.fee_usd), 5.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_swap_btc_to_stable(self, mock_class):
        """Обратный обмен BTC → USDT."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'BTC',
                'from_units': 0.01,
                'to_symbol': 'USDT',
                'to_units': 1000,  # ровно
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        portfolio.refresh_from_db()
        btc = portfolio.assets.get(symbol='BTC')
        usdt = portfolio.assets.get(symbol='USDT')
        self.assertAlmostEqual(float(btc.units), 0.04, places=6)
        self.assertAlmostEqual(float(usdt.units), 2000.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_swap_to_new_asset(self, mock_class):
        """Обмен в монету, которой нет в портфеле — создаётся новый PortfolioAsset."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,
                'to_symbol': 'SOL',  # нет в портфеле, есть в ТОП-10
                'to_units': 0.4,  # 100 / 250
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        sol = PortfolioAsset.objects.get(portfolio=portfolio, symbol='SOL')
        self.assertAlmostEqual(float(sol.units), 0.4, places=6)
        self.assertTrue(sol.is_recommended)
        # initial_price ≈ to_price = 250
        self.assertAlmostEqual(float(sol.initial_price), 250.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_swap_insufficient_units(self, mock_class):
        """from_units > доступно → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100000,
                'to_symbol': 'BTC',
                'to_units': 1.0,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_swap_same_symbol(self, mock_class):
        """from_symbol == to_symbol → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'BTC',
                'from_units': 0.01,
                'to_symbol': 'BTC',
                'to_units': 0.01,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_swap_unsupported_symbol(self, mock_class):
        """Неподдерживаемый символ → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'BTC',
                'from_units': 0.01,
                'to_symbol': 'XYZ123',
                'to_units': 1.0,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_swap_no_active_portfolio(self, mock_class):
        """Без активного портфеля → 404."""
        _setup_price_service_mock(mock_class)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,
                'to_symbol': 'BTC',
                'to_units': 0.001,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('portfolios.views.PriceService')
    def test_swap_finalizes_dca_scale(self, mock_class):
        """В DCA-портфеле после swap units_scale == 1.0."""
        _setup_price_service_mock(mock_class)

        InvestorProfile.objects.create(
            session_id=self.session_id,
            investment_horizon=5,
            investment_amount=Decimal('4000'),
            max_drawdown=20,
            experience_level='medium',
            use_dca=True,
            dca_parts=4,
        )

        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='DCA портфель',
            initial_amount=Decimal('4000'),
            target_years=5,
            is_active=True,
        )
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='USDT',
            name='Tether',
            percentage=Decimal('100'),
            initial_price=Decimal('1'),
            units=Decimal('4000'),
            is_recommended=False,
        )

        from advisor.services import PortfolioAnalyzer
        self.assertLess(PortfolioAnalyzer(portfolio).get_units_scale(), 0.5)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,  # отображаемые units (после scale 0.25 это: 1000 raw → 250 display, 100 < 250 OK)
                'to_symbol': 'BTC',
                'to_units': 0.001,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        portfolio.refresh_from_db()
        # После finalize_dca_scale + swap scale должен быть 1.0
        self.assertAlmostEqual(
            PortfolioAnalyzer(portfolio).get_units_scale(),
            1.0,
            places=4,
        )


# ============ Тесты swap с привязкой к кошельку (PLAN06 — Агент 12) ============


def _create_two_wallets_with_btc(portfolio):
    """Создать два кошелька: на «Холодный» — 0.04 BTC, на «Биржа» — 0.01 BTC.

    Возвращает (cold, exchange).
    Default-кошелёк портфеля при этом сохраняется (он создан backfill-логикой
    через WalletLedger).
    """
    cold = Wallet.objects.create(
        portfolio=portfolio, name='Холодный', type='cold', is_default=False
    )
    exchange = Wallet.objects.create(
        portfolio=portfolio, name='Биржа', type='exchange', is_default=False
    )
    WalletHolding.objects.create(wallet=cold, symbol='BTC', units=Decimal('0.04'))
    WalletHolding.objects.create(wallet=exchange, symbol='BTC', units=Decimal('0.01'))
    WalletHolding.objects.create(
        wallet=exchange, symbol='USDT', units=Decimal('1000')
    )
    return cold, exchange


class SwapWithWalletTests(TestCase):
    """POST /api/portfolio/swap/ с поддержкой wallet_id."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/swap/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_swap_uses_default_wallet_when_wallet_id_omitted(self, mock_class):
        """Без wallet_id swap идёт на default-кошельке, инвариант сохраняется."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 200,
                'to_symbol': 'BTC',
                'to_units': 0.002,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        # default-кошелёк создан и swap привязан к нему
        default_wallet = WalletLedger.get_default_wallet(portfolio)
        swap = PortfolioSwap.objects.get(portfolio=portfolio)
        self.assertEqual(swap.wallet_id, default_wallet.id)

        # Инвариант: PortfolioAsset.units == Σ WalletHolding.units
        for asset in portfolio.assets.all():
            agg = WalletLedger.aggregate_units(portfolio, asset.symbol)
            self.assertAlmostEqual(
                float(asset.units), float(agg), places=8,
                msg=f'инвариант нарушен для {asset.symbol}',
            )

        # Списание/зачисление на default-кошельке
        usdt_holding = WalletHolding.objects.get(wallet=default_wallet, symbol='USDT')
        btc_holding = WalletHolding.objects.get(wallet=default_wallet, symbol='BTC')
        self.assertAlmostEqual(float(usdt_holding.units), 800.0, places=4)
        self.assertAlmostEqual(float(btc_holding.units), 0.052, places=6)

    @patch('portfolios.views.PriceService')
    def test_swap_with_explicit_wallet_id(self, mock_class):
        """Swap на конкретном кошельке: списание и зачисление идут только там."""
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)
        # Подготовим WalletHolding для default-кошелька (как после backfill)
        WalletLedger.ensure_consistent_holdings(portfolio)
        cold, exchange = _create_two_wallets_with_btc(portfolio)
        # На «Биржа» 1000 USDT и 0.01 BTC; меняем 500 USDT → 0.005 BTC

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 500,
                'to_symbol': 'BTC',
                'to_units': 0.005,
                'wallet_id': exchange.id,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        # На «Биржа»: USDT 500, BTC 0.015
        ex_usdt = WalletHolding.objects.get(wallet=exchange, symbol='USDT')
        ex_btc = WalletHolding.objects.get(wallet=exchange, symbol='BTC')
        self.assertAlmostEqual(float(ex_usdt.units), 500.0, places=4)
        self.assertAlmostEqual(float(ex_btc.units), 0.015, places=6)

        # На «Холодный» BTC не изменился
        cold_btc = WalletHolding.objects.get(wallet=cold, symbol='BTC')
        self.assertAlmostEqual(float(cold_btc.units), 0.04, places=6)

        # Swap привязан к exchange-кошельку
        swap = PortfolioSwap.objects.get(portfolio=portfolio)
        self.assertEqual(swap.wallet_id, exchange.id)

        # Инвариант после swap
        for asset in portfolio.assets.all():
            agg = WalletLedger.aggregate_units(portfolio, asset.symbol)
            self.assertAlmostEqual(
                float(asset.units), float(agg), places=8,
                msg=f'инвариант нарушен для {asset.symbol}',
            )

    @patch('portfolios.views.PriceService')
    def test_swap_insufficient_balance_on_specific_wallet(self, mock_class):
        """Баланс проверяется на конкретном кошельке, а не по агрегату.

        Аггрегат = 0.05 BTC (хватает на запрос), но на «Биржа» только 0.01 BTC →
        swap должен упасть с 400.
        """
        _setup_price_service_mock(mock_class)
        portfolio = _create_portfolio_with_btc_usdt(self.session_id)
        WalletLedger.ensure_consistent_holdings(portfolio)
        # default уже содержит 0.05 BTC. Создаём кошелёк «Биржа» с 0.01 BTC,
        # запрашиваем swap 0.02 BTC именно с него — должно упасть.
        exchange = Wallet.objects.create(
            portfolio=portfolio, name='Биржа', type='exchange', is_default=False
        )
        WalletHolding.objects.create(
            wallet=exchange, symbol='BTC', units=Decimal('0.01')
        )

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'BTC',
                'from_units': 0.02,
                'to_symbol': 'USDT',
                'to_units': 2000,
                'wallet_id': exchange.id,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)
        data = response.json()
        self.assertEqual(data.get('wallet_id'), exchange.id)
        self.assertAlmostEqual(float(data.get('units_available') or 0), 0.01, places=6)

        # Балансы не изменились
        ex_btc = WalletHolding.objects.get(wallet=exchange, symbol='BTC')
        self.assertAlmostEqual(float(ex_btc.units), 0.01, places=6)
        self.assertEqual(PortfolioSwap.objects.filter(portfolio=portfolio).count(), 0)

    @patch('portfolios.views.PriceService')
    def test_swap_with_unknown_wallet_id(self, mock_class):
        """Несуществующий wallet_id → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,
                'to_symbol': 'BTC',
                'to_units': 0.001,
                'wallet_id': 9999999,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_swap_with_other_portfolio_wallet_id(self, mock_class):
        """wallet_id чужого портфеля → 400."""
        _setup_price_service_mock(mock_class)
        _create_portfolio_with_btc_usdt(self.session_id)

        # Сторонний портфель + его кошелёк
        other_session = str(uuid.uuid4())
        other_portfolio = Portfolio.objects.create(
            session_id=other_session,
            name='Чужой',
            initial_amount=Decimal('1000'),
            target_years=5,
            is_active=False,
        )
        other_wallet = Wallet.objects.create(
            portfolio=other_portfolio, name='чужой', type='other', is_default=True
        )

        response = self.client.post(
            self.url,
            {
                'from_symbol': 'USDT',
                'from_units': 100,
                'to_symbol': 'BTC',
                'to_units': 0.001,
                'wallet_id': other_wallet.id,
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
