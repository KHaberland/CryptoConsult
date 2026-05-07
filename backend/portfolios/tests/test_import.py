"""
Тесты импорта существующего портфеля пользователя
(endpoints: GET /api/portfolio/top10/, POST /api/portfolio/import/).
"""

import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from portfolios.models import Portfolio, PortfolioAsset


# Фикстура «топ-15 монет с CoinGecko» (включая стейблы — будут отфильтрованы).
MOCK_TOP_COINS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'market_cap': 1_500_000_000_000, 'current_price': 100000.0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'market_cap': 400_000_000_000, 'current_price': 3500.0},
    {'symbol': 'USDT', 'name': 'Tether', 'market_cap': 130_000_000_000, 'current_price': 1.0},
    {'symbol': 'BNB', 'name': 'BNB', 'market_cap': 90_000_000_000, 'current_price': 700.0},
    {'symbol': 'SOL', 'name': 'Solana', 'market_cap': 80_000_000_000, 'current_price': 250.0},
    {'symbol': 'USDC', 'name': 'USD Coin', 'market_cap': 50_000_000_000, 'current_price': 1.0},
    {'symbol': 'XRP', 'name': 'XRP', 'market_cap': 40_000_000_000, 'current_price': 3.0},
    {'symbol': 'DOGE', 'name': 'Dogecoin', 'market_cap': 30_000_000_000, 'current_price': 0.4},
    {'symbol': 'ADA', 'name': 'Cardano', 'market_cap': 20_000_000_000, 'current_price': 1.0},
    {'symbol': 'TRX', 'name': 'TRON', 'market_cap': 18_000_000_000, 'current_price': 0.25},
    {'symbol': 'LINK', 'name': 'Chainlink', 'market_cap': 15_000_000_000, 'current_price': 25.0},
    {'symbol': 'DOT', 'name': 'Polkadot', 'market_cap': 12_000_000_000, 'current_price': 8.0},
    {'symbol': 'AVAX', 'name': 'Avalanche', 'market_cap': 10_000_000_000, 'current_price': 35.0},
    {'symbol': 'MATIC', 'name': 'Polygon', 'market_cap': 8_000_000_000, 'current_price': 1.2},
    {'symbol': 'LTC', 'name': 'Litecoin', 'market_cap': 7_000_000_000, 'current_price': 90.0},
]

MOCK_PRICES = {
    'BTC': 100000.0,
    'ETH': 3500.0,
    'BNB': 700.0,
    'SOL': 250.0,
    'XRP': 3.0,
    'SHIB': 0.00002,
    'DOGE': 0.4,
}

# Поддерживаемые символы для мока is_symbol_supported (имитация SYMBOL_TO_ID)
SUPPORTED_SYMBOLS = frozenset({
    'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'TRX', 'DOT', 'LINK',
    'AVAX', 'MATIC', 'LTC', 'USDT', 'USDC', 'SHIB',
})


def _setup_price_service_class_mock(mock_class):
    """
    Настроить MagicMock-класс PriceService:
    - Класс-методы (is_symbol_supported) возвращают реальную логику.
    - Экземпляр через mock_class() — MagicMock с типовыми возвращаемыми значениями.
    """
    mock_class.is_symbol_supported.side_effect = (
        lambda symbol: (symbol or '').upper() in SUPPORTED_SYMBOLS
    )

    mock_service = MagicMock()
    mock_service.fetch_top_coins_from_coingecko.return_value = MOCK_TOP_COINS
    # Симулируем реальную фильтрацию ТОП-10 без стейблов
    mock_service.get_top10_recommended_symbols.return_value = [
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE', 'ADA', 'TRX', 'LINK', 'DOT'
    ]
    mock_service.get_top10_recommended_assets.return_value = [
        {
            'symbol': c['symbol'],
            'name': c['name'],
            'current_price': c['current_price'],
            'market_cap': c['market_cap'],
        }
        for c in MOCK_TOP_COINS
        if c['symbol'].lower() not in ('usdt', 'usdc', 'busd', 'dai')
    ][:10]
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_class.return_value = mock_service
    return mock_service


class PortfolioTop10EndpointTests(TestCase):
    """Тесты GET /api/portfolio/top10/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_top10_returns_ten_coins_without_stables(self, mock_price_class):
        """ТОП-10 возвращает ровно 10 монет, без стейблкоинов."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.get('/api/portfolio/top10/', **self._headers())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['count'], 10)
        symbols = [a['symbol'] for a in data['top10']]
        self.assertIn('BTC', symbols)
        self.assertIn('ETH', symbols)
        self.assertNotIn('USDT', symbols)
        self.assertNotIn('USDC', symbols)

    @patch('portfolios.views.PriceService')
    def test_top10_assets_have_required_fields(self, mock_price_class):
        """Каждая монета в ответе имеет symbol, name, current_price, market_cap."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.get('/api/portfolio/top10/', **self._headers())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for asset in response.json()['top10']:
            self.assertIn('symbol', asset)
            self.assertIn('name', asset)
            self.assertIn('current_price', asset)
            self.assertIn('market_cap', asset)


class PortfolioImportEndpointTests(TestCase):
    """Тесты POST /api/portfolio/import/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/import/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_import_only_top10(self, mock_price_class):
        """Импорт портфеля только из монет ТОП-10 — без warnings."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'name': 'Импорт BTC + ETH',
                'target_years': 5,
                'assets': [
                    {'symbol': 'BTC', 'units': 0.1, 'purchase_price': 60000},
                    {'symbol': 'ETH', 'units': 1.0, 'purchase_price': 2000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['portfolio']['is_imported'])
        self.assertEqual(len(data['non_recommended']), 0)
        self.assertEqual(len(data['warnings']), 0)

        portfolio = Portfolio.objects.get(session_id=self.session_id)
        self.assertEqual(portfolio.assets.count(), 2)
        # initial_amount = 0.1*60000 + 1.0*2000 = 8000
        self.assertAlmostEqual(float(portfolio.initial_amount), 8000.0, places=2)
        # Доли — по текущей рыночной стоимости (BTC=10000, ETH=3500 → 74.07%/25.93%)
        btc_asset = portfolio.assets.get(symbol='BTC')
        eth_asset = portfolio.assets.get(symbol='ETH')
        self.assertTrue(btc_asset.is_recommended)
        self.assertTrue(eth_asset.is_recommended)
        self.assertAlmostEqual(
            float(btc_asset.percentage) + float(eth_asset.percentage),
            100.0,
            places=1,
        )

    @patch('portfolios.views.PriceService')
    def test_import_with_non_top10_returns_warning(self, mock_price_class):
        """Импорт с альткойном вне ТОП-10 — выдаём предупреждение, но импорт успешен."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 3,
                'assets': [
                    {'symbol': 'BTC', 'units': 0.05},
                    {'symbol': 'SHIB', 'units': 1_000_000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(len(data['non_recommended']), 1)
        self.assertEqual(data['non_recommended'][0]['symbol'], 'SHIB')
        self.assertIn('обмен', data['non_recommended'][0]['message'].lower())

        shib_asset = PortfolioAsset.objects.get(symbol='SHIB')
        self.assertFalse(shib_asset.is_recommended)
        btc_asset = PortfolioAsset.objects.get(symbol='BTC')
        self.assertTrue(btc_asset.is_recommended)

    @patch('portfolios.views.PriceService')
    def test_import_unsupported_symbol_returns_warning(self, mock_price_class):
        """Полностью неизвестный символ → попадает в warnings и не сохраняется."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    {'symbol': 'BTC', 'units': 0.1},
                    {'symbol': 'XYZ123', 'units': 100},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        warning_symbols = [w['symbol'] for w in data['warnings']]
        self.assertIn('XYZ123', warning_symbols)
        # XYZ123 не должен попасть в активы
        self.assertFalse(
            PortfolioAsset.objects.filter(symbol='XYZ123').exists()
        )
        self.assertTrue(
            PortfolioAsset.objects.filter(symbol='BTC').exists()
        )

    @patch('portfolios.views.PriceService')
    def test_import_value_usd_input(self, mock_price_class):
        """Ввод суммы в долларах вместо units — рассчитывается по текущей цене."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    {'symbol': 'BTC', 'value_usd': 5000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        asset = PortfolioAsset.objects.get(
            portfolio__session_id=self.session_id,
            symbol='BTC',
        )
        # 5000 / 100000 = 0.05 BTC
        self.assertAlmostEqual(float(asset.units), 0.05, places=6)

    @patch('portfolios.views.PriceService')
    def test_cannot_import_when_active_portfolio_exists(self, mock_price_class):
        """Если уже есть активный портфель — импорт отклоняется (400)."""
        _setup_price_service_class_mock(mock_price_class)

        Portfolio.objects.create(
            session_id=self.session_id,
            initial_amount=Decimal('1000'),
            target_years=5,
            is_active=True,
        )

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [{'symbol': 'BTC', 'units': 0.1}],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.json())

    @patch('portfolios.views.PriceService')
    def test_import_empty_assets_returns_400(self, mock_price_class):
        """Пустой список активов → 400."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {'target_years': 5, 'assets': []},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('portfolios.views.PriceService')
    def test_import_all_unsupported_returns_400(self, mock_price_class):
        """Если все указанные символы не поддерживаются — 400."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    {'symbol': 'XYZ123', 'units': 100},
                    {'symbol': 'ABC', 'units': 100},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('warnings', response.json())

    @patch('portfolios.views.PriceService')
    def test_import_summary_calculates_pl(self, mock_price_class):
        """summary.profit_loss = (units * current_price) - (units * purchase_price)."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    # Купили BTC по 60000, текущая цена 100000 → +4000 на 0.1 BTC
                    {'symbol': 'BTC', 'units': 0.1, 'purchase_price': 60000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        summary = response.json()['summary']
        self.assertAlmostEqual(summary['total_initial'], 6000.0, places=2)
        self.assertAlmostEqual(summary['total_current'], 10000.0, places=2)
        self.assertAlmostEqual(summary['profit_loss'], 4000.0, places=2)
        # (10000 - 6000) / 6000 * 100 ≈ 66.67%
        self.assertAlmostEqual(summary['profit_loss_percent'], 66.67, places=1)

    @patch('portfolios.views.PriceService')
    def test_import_purchased_at_saved(self, mock_price_class):
        """Поле purchased_at сохраняется в PortfolioAsset."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    {
                        'symbol': 'BTC',
                        'units': 0.05,
                        'purchase_price': 50000,
                        'purchased_at': '2024-03-15',
                    },
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        asset = PortfolioAsset.objects.get(symbol='BTC')
        self.assertEqual(str(asset.purchased_at), '2024-03-15')

    @patch('portfolios.views.PriceService')
    def test_import_uses_current_price_when_purchase_price_omitted(
        self, mock_price_class
    ):
        """Если purchase_price не указана, берётся текущая цена."""
        _setup_price_service_class_mock(mock_price_class)

        response = self.client.post(
            self.url,
            {
                'target_years': 5,
                'assets': [
                    {'symbol': 'BTC', 'units': 0.1},  # без purchase_price
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # initial_amount = 0.1 * 100000 = 10000 (= current_value, profit_loss=0)
        portfolio = Portfolio.objects.get(session_id=self.session_id)
        self.assertAlmostEqual(float(portfolio.initial_amount), 10000.0, places=2)
        summary = response.json()['summary']
        self.assertAlmostEqual(summary['profit_loss'], 0.0, places=2)


class AdvisorPromptForImportedPortfolioTests(TestCase):
    """
    Системный промпт AI-консультанта должен учитывать факт импорта:
    добавлять блок «ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ» и перечислять активы вне ТОП-10.
    """

    def setUp(self):
        self.session_id = str(uuid.uuid4())

    def _make_portfolio(self, is_imported: bool, with_non_recommended: bool):
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Test',
            initial_amount=Decimal('10000'),
            target_years=5,
            is_active=True,
            is_imported=is_imported,
        )
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='BTC',
            name='Bitcoin',
            percentage=Decimal('70'),
            initial_price=Decimal('100000'),
            units=Decimal('0.07'),
            is_recommended=True,
        )
        if with_non_recommended:
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol='SHIB',
                name='Shiba Inu',
                percentage=Decimal('30'),
                initial_price=Decimal('0.00002'),
                units=Decimal('150000000'),
                is_recommended=False,
            )
        else:
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol='ETH',
                name='Ethereum',
                percentage=Decimal('30'),
                initial_price=Decimal('3500'),
                units=Decimal('0.857'),
                is_recommended=True,
            )
        return portfolio

    def _build_prompt(self):
        from advisor.services import AIAdvisorService
        with patch.object(
            AIAdvisorService, '__init__', lambda self, *a, **kw: None,
        ):
            advisor = AIAdvisorService()
        # Минимально инициализируем зависимые поля
        advisor.price_service = MagicMock()
        # Подменяем PortfolioAnalyzer на быстрый стаб
        with patch('advisor.services.PortfolioAnalyzer') as mock_analyzer_class:
            instance = MagicMock()
            instance.get_current_value.return_value = {
                'initial_value': 10000.0,
                'current_value': 12000.0,
                'profit_loss': 2000.0,
                'profit_loss_percent': 20.0,
                'assets': [
                    {
                        'symbol': 'BTC', 'name': 'Bitcoin',
                        'percentage': 70.0, 'initial_value': 7000.0,
                        'current_value': 8400.0, 'current_price': 100000.0,
                        'change_24h': 0.0, 'profit_loss': 1400.0,
                        'profit_loss_percent': 20.0, 'is_recommended': True,
                    },
                    {
                        'symbol': 'SHIB', 'name': 'Shiba Inu',
                        'percentage': 30.0, 'initial_value': 3000.0,
                        'current_value': 3600.0, 'current_price': 0.00002,
                        'change_24h': 0.0, 'profit_loss': 600.0,
                        'profit_loss_percent': 20.0, 'is_recommended': False,
                    },
                ],
            }
            instance.get_drawdown.return_value = {
                'current_drawdown': 0.0,
                'peak_value': 12000.0,
                'current_value': 12000.0,
                'base_value': 10000.0,
            }
            from datetime import date as _date, timedelta as _td
            instance.get_time_metrics.return_value = {
                'start_date': _date.today() - _td(days=60),
                'target_date': _date.today() + _td(days=300),
                'days_active': 60,
                'days_remaining': 300,
                'progress_percent': 16.7,
                'months_active': 2.0,
                'can_consider_exit': False,
            }
            mock_analyzer_class.return_value = instance
            return advisor.get_system_prompt(self.session_id)

    def test_imported_portfolio_prompt_contains_marker(self):
        """Импортированный портфель → промпт содержит блок ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ."""
        self._make_portfolio(is_imported=True, with_non_recommended=True)
        prompt = self._build_prompt()
        self.assertIn('ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ', prompt)
        self.assertIn('Импортированный', prompt)
        self.assertIn('SHIB', prompt)

    def test_non_imported_portfolio_prompt_no_import_block(self):
        """Обычный портфель → блока про импорт быть не должно."""
        self._make_portfolio(is_imported=False, with_non_recommended=False)
        prompt = self._build_prompt()
        self.assertNotIn('ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ', prompt)
        self.assertIn('Создан с нуля по методике сервиса', prompt)

    def _make_portfolio_with_usdc(
        self,
        usdc_percentage: Decimal,
        btc_percentage: Decimal,
        with_other_non_recommended: bool = False,
    ):
        """
        Импортированный портфель: BTC + USDC (и опционально SHIB как
        реальный «вне ТОП-10»).
        """
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Test USDC',
            initial_amount=Decimal('10000'),
            target_years=5,
            is_active=True,
            is_imported=True,
        )
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='BTC',
            name='Bitcoin',
            percentage=btc_percentage,
            initial_price=Decimal('100000'),
            units=Decimal('0.07'),
            is_recommended=True,
        )
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='USDC',
            name='USD Coin',
            percentage=usdc_percentage,
            initial_price=Decimal('1'),
            units=Decimal('1000'),
            is_recommended=False,
        )
        if with_other_non_recommended:
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol='SHIB',
                name='Shiba Inu',
                percentage=Decimal('5'),
                initial_price=Decimal('0.00002'),
                units=Decimal('25000000'),
                is_recommended=False,
            )
        return portfolio

    def _build_prompt_with_assets(self, assets):
        """
        Версия `_build_prompt`, которая принимает готовый список assets,
        чтобы тестировать произвольные составы портфеля (в т.ч. с USDC).
        """
        from advisor.services import AIAdvisorService
        with patch.object(
            AIAdvisorService, '__init__', lambda self, *a, **kw: None,
        ):
            advisor = AIAdvisorService()
        advisor.price_service = MagicMock()
        with patch('advisor.services.PortfolioAnalyzer') as mock_analyzer_class:
            instance = MagicMock()
            instance.get_current_value.return_value = {
                'initial_value': 10000.0,
                'current_value': 12000.0,
                'profit_loss': 2000.0,
                'profit_loss_percent': 20.0,
                'assets': assets,
            }
            instance.get_drawdown.return_value = {
                'current_drawdown': 0.0,
                'peak_value': 12000.0,
                'current_value': 12000.0,
                'base_value': 10000.0,
            }
            from datetime import date as _date, timedelta as _td
            instance.get_time_metrics.return_value = {
                'start_date': _date.today() - _td(days=60),
                'target_date': _date.today() + _td(days=300),
                'days_active': 60,
                'days_remaining': 300,
                'progress_percent': 16.7,
                'months_active': 2.0,
                'can_consider_exit': False,
            }
            mock_analyzer_class.return_value = instance
            return advisor.get_system_prompt(self.session_id)

    def test_imported_portfolio_with_usdc_has_strategic_cash_block(self):
        """USDC в импортированном портфеле → блок «USDC — СТРАТЕГИЧЕСКИЙ КЭШ»
        и USDC исключён из строки активов «вне ТОП-10»."""
        self._make_portfolio_with_usdc(
            usdc_percentage=Decimal('10'),
            btc_percentage=Decimal('90'),
        )
        assets = [
            {
                'symbol': 'BTC', 'name': 'Bitcoin',
                'percentage': 90.0, 'initial_value': 9000.0,
                'current_value': 10800.0, 'current_price': 100000.0,
                'change_24h': 0.0, 'profit_loss': 1800.0,
                'profit_loss_percent': 20.0, 'is_recommended': True,
            },
            {
                'symbol': 'USDC', 'name': 'USD Coin',
                'percentage': 10.0, 'initial_value': 1000.0,
                'current_value': 1000.0, 'current_price': 1.0,
                'change_24h': 0.0, 'profit_loss': 0.0,
                'profit_loss_percent': 0.0, 'is_recommended': False,
            },
        ]
        prompt = self._build_prompt_with_assets(assets)

        self.assertIn('ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ', prompt)
        self.assertIn('USDC — СТРАТЕГИЧЕСКИЙ КЭШ', prompt)
        self.assertIn('5–15%', prompt)
        # USDC не должен попадать в список активов «вне ТОП-10»:
        self.assertIn(
            'Активы вне ТОП-10 ликвидных в этом портфеле (без учёта USDC): нет',
            prompt,
        )
        # Финальная инструкция «рекомендуй обмен на ТОП-10» не должна
        # появляться, если кроме USDC других не-ТОП-10 активов нет.
        self.assertNotIn(
            'рекомендуй обмен на актив из ТОП-10', prompt,
        )

    def test_imported_portfolio_with_usdc_and_altcoin_keeps_both_blocks(self):
        """USDC + SHIB → есть оба блока: про USDC и про активы вне ТОП-10."""
        self._make_portfolio_with_usdc(
            usdc_percentage=Decimal('10'),
            btc_percentage=Decimal('85'),
            with_other_non_recommended=True,
        )
        assets = [
            {
                'symbol': 'BTC', 'name': 'Bitcoin',
                'percentage': 85.0, 'initial_value': 8500.0,
                'current_value': 10200.0, 'current_price': 100000.0,
                'change_24h': 0.0, 'profit_loss': 1700.0,
                'profit_loss_percent': 20.0, 'is_recommended': True,
            },
            {
                'symbol': 'USDC', 'name': 'USD Coin',
                'percentage': 10.0, 'initial_value': 1000.0,
                'current_value': 1000.0, 'current_price': 1.0,
                'change_24h': 0.0, 'profit_loss': 0.0,
                'profit_loss_percent': 0.0, 'is_recommended': False,
            },
            {
                'symbol': 'SHIB', 'name': 'Shiba Inu',
                'percentage': 5.0, 'initial_value': 500.0,
                'current_value': 600.0, 'current_price': 0.00002,
                'change_24h': 0.0, 'profit_loss': 100.0,
                'profit_loss_percent': 20.0, 'is_recommended': False,
            },
        ]
        prompt = self._build_prompt_with_assets(assets)

        self.assertIn('USDC — СТРАТЕГИЧЕСКИЙ КЭШ', prompt)
        self.assertIn('SHIB', prompt)
        self.assertIn('рекомендуй обмен на актив из ТОП-10', prompt)
        # USDC не должен фигурировать в самом ПЕРЕЧНЕ активов «вне ТОП-10»
        # (часть строки после двоеточия). В подписи слева "(без учёта USDC)"
        # символы USDC присутствовать могут.
        non_rec_line = next(
            (
                line for line in prompt.splitlines()
                if line.startswith('Активы вне ТОП-10 ликвидных в этом портфеле')
            ),
            '',
        )
        non_rec_list = non_rec_line.split(':', 1)[1] if ':' in non_rec_line else ''
        self.assertIn('SHIB', non_rec_list)
        self.assertNotIn('USDC', non_rec_list)
