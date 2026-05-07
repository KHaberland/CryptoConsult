"""
Тесты пополнения портфеля в режиме «по монетам»
(POST /api/portfolio/contribute/ с body = { "items": [...] }).
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
    PortfolioContributionItem,
    Wallet,
    WalletHolding,
)
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
    'TRX': 0.25,
    'SHIB': 0.00002,
}

MOCK_TOP10 = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'DOT']


def _setup_price_service_mock(mock_class):
    """Стандартный мок PriceService для тестов contribute_by_units."""
    mock_service = MagicMock()
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_service.get_top10_recommended_symbols.return_value = MOCK_TOP10
    mock_service.get_top10_recommended_assets.return_value = [
        {'symbol': s, 'name': s, 'current_price': MOCK_PRICES.get(s, 0), 'market_cap': 0}
        for s in MOCK_TOP10
    ]
    mock_class.return_value = mock_service
    return mock_service


class ContributeByUnitsTests(TestCase):
    """POST /api/portfolio/contribute/ — режим «по монетам»."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/contribute/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _create_portfolio(self, with_btc=True, with_eth=True):
        """Создать активный портфель с BTC/ETH (без DCA-профиля)."""
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Тестовый портфель',
            initial_amount=Decimal('10000'),
            target_years=5,
            is_active=True,
        )
        if with_btc:
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol='BTC',
                name='Bitcoin',
                percentage=Decimal('70'),
                initial_price=Decimal('80000'),
                units=Decimal('0.0875'),
                is_recommended=True,
            )
        if with_eth:
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol='ETH',
                name='Ethereum',
                percentage=Decimal('30'),
                initial_price=Decimal('3000'),
                units=Decimal('1.0'),
                is_recommended=True,
            )
        return portfolio

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_existing_asset(self, mock_class):
        """Докупка в существующий BTC: units растут, средневзвешенная цена корректна."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.05, 'purchase_price': 90000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        # 0.0875 + 0.05 = 0.1375
        self.assertAlmostEqual(float(btc.units), 0.1375, places=6)

        # Средневзвешенная: (0.0875 * 80000 + 0.05 * 90000) / 0.1375
        expected_price = (0.0875 * 80000 + 0.05 * 90000) / 0.1375
        self.assertAlmostEqual(float(btc.initial_price), expected_price, places=2)

        portfolio.refresh_from_db()
        # initial_amount += 0.05 * 90000 = 4500
        self.assertAlmostEqual(float(portfolio.initial_amount), 14500.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_new_asset_in_top10(self, mock_class):
        """Добавление SOL (есть в ТОП-10): создаётся новый актив с is_recommended=True."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'SOL', 'units': 4.0},  # purchase_price берётся текущим
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        sol = PortfolioAsset.objects.get(portfolio=portfolio, symbol='SOL')
        self.assertTrue(sol.is_recommended)
        self.assertAlmostEqual(float(sol.units), 4.0, places=6)
        # purchase_price взят из MOCK_PRICES = 250
        self.assertAlmostEqual(float(sol.initial_price), 250.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_alt_outside_top10(self, mock_class):
        """Добавление SHIB (не в ТОП-10): is_recommended=False."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'SHIB', 'units': 1_000_000.0},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        shib = PortfolioAsset.objects.get(portfolio=portfolio, symbol='SHIB')
        self.assertFalse(shib.is_recommended)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_recomputes_percentages(self, mock_class):
        """После операции Σ percentage ≈ 100 и доли соответствуют рынку."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'SOL', 'units': 10.0},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        portfolio.refresh_from_db()
        total_pct = sum(float(a.percentage) for a in portfolio.assets.all())
        self.assertAlmostEqual(total_pct, 100.0, places=1)

        # Рыночная стоимость:
        # BTC: 0.0875 * 100000 = 8750
        # ETH: 1.0 * 3500 = 3500
        # SOL: 10.0 * 250 = 2500
        # total = 14750
        # BTC% ≈ 59.32, ETH% ≈ 23.73, SOL% ≈ 16.95
        btc = portfolio.assets.get(symbol='BTC')
        sol = portfolio.assets.get(symbol='SOL')
        self.assertAlmostEqual(float(btc.percentage), 8750 / 14750 * 100, places=0)
        self.assertAlmostEqual(float(sol.percentage), 2500 / 14750 * 100, places=0)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_invalid_symbol(self, mock_class):
        """Неизвестный символ → 400."""
        _setup_price_service_mock(mock_class)
        self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'XYZ123', 'units': 1.0},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_zero_units(self, mock_class):
        """Нулевое количество units → 400."""
        _setup_price_service_mock(mock_class)
        self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.0},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_creates_contribution_item(self, mock_class):
        """Создаются записи PortfolioContribution и PortfolioContributionItem."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.01, 'purchase_price': 95000},
                    {'symbol': 'ETH', 'units': 0.5, 'purchase_price': 3200},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        contributions = PortfolioContribution.objects.filter(portfolio=portfolio)
        self.assertEqual(contributions.count(), 1)
        contribution = contributions.first()
        # value_usd = 0.01 * 95000 + 0.5 * 3200 = 950 + 1600 = 2550
        self.assertAlmostEqual(float(contribution.amount), 2550.0, places=2)

        items = PortfolioContributionItem.objects.filter(contribution=contribution)
        self.assertEqual(items.count(), 2)
        symbols = {it.symbol for it in items}
        self.assertEqual(symbols, {'BTC', 'ETH'})

        btc_item = items.get(symbol='BTC')
        self.assertAlmostEqual(float(btc_item.units), 0.01, places=6)
        self.assertAlmostEqual(float(btc_item.purchase_price), 95000.0, places=2)
        self.assertAlmostEqual(float(btc_item.value_usd), 950.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_finalizes_dca_scale(self, mock_class):
        """В DCA-портфеле после операции units_scale становится 1.0."""
        _setup_price_service_mock(mock_class)

        # Создаём DCA-профиль: investment_amount = 4000, parts = 4 → first_part = 1000
        InvestorProfile.objects.create(
            session_id=self.session_id,
            investment_horizon=5,
            investment_amount=Decimal('4000'),
            max_drawdown=20,
            experience_level='medium',  # не beginner, чтобы dca_parts не переопределилось
            use_dca=True,
            dca_parts=4,
        )

        # Портфель создан с полной суммой 4000 (как в текущей логике DCA)
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='DCA портфель',
            initial_amount=Decimal('4000'),
            target_years=5,
            is_active=True,
        )
        # 0.04 BTC по 100k = $4000 в RAW units
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='BTC',
            name='Bitcoin',
            percentage=Decimal('100'),
            initial_price=Decimal('100000'),
            units=Decimal('0.04'),
            is_recommended=True,
        )

        # Проверяем, что scale активен (≈ 0.25)
        from advisor.services import PortfolioAnalyzer
        analyzer_before = PortfolioAnalyzer(portfolio)
        self.assertLess(analyzer_before.get_units_scale(), 0.5)

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.005, 'purchase_price': 100000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        portfolio.refresh_from_db()
        analyzer_after = PortfolioAnalyzer(portfolio)
        # После finalize_dca_scale + новой операции scale должен стать 1.0
        self.assertAlmostEqual(analyzer_after.get_units_scale(), 1.0, places=4)

        # Проверяем, что initial_amount уже не равен investment_amount
        self.assertNotAlmostEqual(
            float(portfolio.initial_amount),
            4000.0,
            places=1,
        )

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_no_active_portfolio(self, mock_class):
        """Без активного портфеля → 404."""
        _setup_price_service_mock(mock_class)

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.1},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_units_default_purchase_price_is_market(self, mock_class):
        """Если purchase_price не указан — берётся текущая рыночная цена."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio(with_btc=False, with_eth=True)

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.01},  # без purchase_price
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        # purchase_price = MOCK_PRICES['BTC'] = 100000
        self.assertAlmostEqual(float(btc.initial_price), 100000.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_contribute_by_amount_still_works(self, mock_class):
        """Старый формат `{ "amount": <usd> }` (DCA) продолжает работать."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {'amount': 1000},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        contributions = PortfolioContribution.objects.filter(portfolio=portfolio)
        self.assertEqual(contributions.count(), 1)
        self.assertAlmostEqual(float(contributions.first().amount), 1000.0, places=2)

    @patch('portfolios.views.PriceService')
    def test_contribute_creates_default_wallet_if_missing(self, mock_class):
        """Если у портфеля нет default-кошелька — он создастся автоматически."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        # До запроса нет ни одного кошелька (тестовая БД, миграция backfill — no-op)
        self.assertEqual(Wallet.objects.filter(portfolio=portfolio).count(), 0)

        response = self.client.post(
            self.url,
            {'items': [{'symbol': 'BTC', 'units': 0.05, 'purchase_price': 90000}]},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        wallets = Wallet.objects.filter(portfolio=portfolio)
        self.assertEqual(wallets.count(), 1)
        default_wallet = wallets.first()
        self.assertTrue(default_wallet.is_default)
        self.assertEqual(default_wallet.name, 'Общий кошелёк')

    @patch('portfolios.views.PriceService')
    def test_contribute_invariant_holding_sum_equals_asset_units(self, mock_class):
        """После contribute Σ WalletHolding.units == PortfolioAsset.units (инвариант)."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        response = self.client.post(
            self.url,
            {'items': [
                {'symbol': 'BTC', 'units': 0.05, 'purchase_price': 90000},
                {'symbol': 'SOL', 'units': 4.0},
            ]},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        for asset in portfolio.assets.all():
            aggregate = sum(
                (h.units for h in WalletHolding.objects.filter(
                    wallet__portfolio=portfolio, symbol=asset.symbol
                )),
                Decimal('0'),
            )
            self.assertEqual(
                aggregate, asset.units,
                f'Σ WalletHolding.units != PortfolioAsset.units для {asset.symbol}',
            )

    @patch('portfolios.views.PriceService')
    def test_contribute_with_explicit_wallet_id(self, mock_class):
        """С явным wallet_id units попадают именно в указанный кошелёк."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        # Создаём два кошелька: default и второй (биржа).
        default_wallet = Wallet.objects.create(
            portfolio=portfolio, name='Общий кошелёк', type='other', is_default=True,
        )
        exchange_wallet = Wallet.objects.create(
            portfolio=portfolio, name='Binance', type='exchange', is_default=False,
        )

        response = self.client.post(
            self.url,
            {
                'wallet_id': exchange_wallet.id,
                'items': [{'symbol': 'BTC', 'units': 0.05, 'purchase_price': 90000}],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        # На бирже должно быть ровно 0.05 BTC, в default — backfilled 0.0875.
        ex_holding = WalletHolding.objects.get(wallet=exchange_wallet, symbol='BTC')
        self.assertAlmostEqual(float(ex_holding.units), 0.05, places=8)

        def_holding = WalletHolding.objects.get(wallet=default_wallet, symbol='BTC')
        self.assertAlmostEqual(float(def_holding.units), 0.0875, places=8)

        # Σ = 0.0875 + 0.05 = 0.1375 — совпадает с PortfolioAsset.units.
        btc = PortfolioAsset.objects.get(portfolio=portfolio, symbol='BTC')
        self.assertAlmostEqual(float(btc.units), 0.1375, places=8)

    @patch('portfolios.views.PriceService')
    def test_contribute_rejects_foreign_wallet_id(self, mock_class):
        """wallet_id чужого портфеля → 400."""
        _setup_price_service_mock(mock_class)
        portfolio = self._create_portfolio()

        # Создаём кошелёк в другом портфеле.
        other_portfolio = Portfolio.objects.create(
            session_id=str(uuid.uuid4()),
            name='Чужой портфель',
            initial_amount=Decimal('1000'),
            target_years=1,
            is_active=True,
        )
        other_wallet = Wallet.objects.create(
            portfolio=other_portfolio, name='Foreign', type='other', is_default=True,
        )

        response = self.client.post(
            self.url,
            {
                'wallet_id': other_wallet.id,
                'items': [{'symbol': 'BTC', 'units': 0.01}],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # И ничего не записалось в наш портфель.
        self.assertEqual(
            PortfolioContribution.objects.filter(portfolio=portfolio).count(), 0
        )
