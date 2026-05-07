"""
Тесты списка монет, доступных для пополнения / обмена в портфеле
(GET /api/portfolio/tradable-assets/) и метода
PriceService.get_available_for_trade.
"""

import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from portfolios.models import Portfolio, PortfolioAsset
from portfolios.services import PriceService


MOCK_TOP10_ASSETS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'current_price': 100000.0, 'market_cap': 0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'current_price': 3500.0, 'market_cap': 0},
    {'symbol': 'BNB', 'name': 'BNB', 'current_price': 700.0, 'market_cap': 0},
    {'symbol': 'SOL', 'name': 'Solana', 'current_price': 250.0, 'market_cap': 0},
    {'symbol': 'XRP', 'name': 'XRP', 'current_price': 3.0, 'market_cap': 0},
    {'symbol': 'DOGE', 'name': 'Dogecoin', 'current_price': 0.4, 'market_cap': 0},
    {'symbol': 'ADA', 'name': 'Cardano', 'current_price': 1.0, 'market_cap': 0},
    {'symbol': 'TRX', 'name': 'TRON', 'current_price': 0.25, 'market_cap': 0},
    {'symbol': 'LINK', 'name': 'Chainlink', 'current_price': 25.0, 'market_cap': 0},
    {'symbol': 'DOT', 'name': 'Polkadot', 'current_price': 8.0, 'market_cap': 0},
]

MOCK_PRICES = {
    a['symbol']: a['current_price'] for a in MOCK_TOP10_ASSETS
}
MOCK_PRICES['USDT'] = 1.0
MOCK_PRICES['USDC'] = 1.0
MOCK_PRICES['SHIB'] = 0.00002


class TradableAssetsServiceTests(TestCase):
    """Юнит-тесты PriceService.get_available_for_trade."""

    @patch.object(PriceService, 'get_top10_recommended_assets')
    @patch.object(PriceService, 'get_prices')
    def test_includes_portfolio_top10_stables(self, mock_get_prices, mock_top10):
        """Объединение портфельных + ТОП-10 + стейблкоинов с правильными метками."""
        mock_top10.return_value = MOCK_TOP10_ASSETS
        mock_get_prices.return_value = MOCK_PRICES

        # Портфель содержит SHIB (не в ТОП-10, не стейбл) и BTC (в ТОП-10).
        portfolio_symbols = ['BTC', 'SHIB']
        result = PriceService().get_available_for_trade(portfolio_symbols)

        symbols = {item['symbol'] for item in result}
        # BTC, SHIB (из портфеля)
        self.assertIn('BTC', symbols)
        self.assertIn('SHIB', symbols)
        # ТОП-10
        for top_sym in ['ETH', 'BNB', 'SOL', 'XRP', 'DOGE']:
            self.assertIn(top_sym, symbols)
        # Стейблкоины
        self.assertIn('USDT', symbols)
        self.assertIn('USDC', symbols)

        items_by_symbol = {item['symbol']: item for item in result}

        # Метка in_portfolio
        self.assertTrue(items_by_symbol['BTC']['in_portfolio'])
        self.assertTrue(items_by_symbol['SHIB']['in_portfolio'])
        self.assertFalse(items_by_symbol['ETH']['in_portfolio'])
        self.assertFalse(items_by_symbol['USDT']['in_portfolio'])

        # Метка is_recommended (в ТОП-10)
        self.assertTrue(items_by_symbol['BTC']['is_recommended'])
        self.assertTrue(items_by_symbol['ETH']['is_recommended'])
        self.assertFalse(items_by_symbol['SHIB']['is_recommended'])
        self.assertFalse(items_by_symbol['USDT']['is_recommended'])

        # Метка is_stable
        self.assertTrue(items_by_symbol['USDT']['is_stable'])
        self.assertTrue(items_by_symbol['USDC']['is_stable'])
        self.assertFalse(items_by_symbol['BTC']['is_stable'])

        # Цены подтянулись из get_prices
        self.assertAlmostEqual(items_by_symbol['BTC']['current_price'], 100000.0, places=2)
        self.assertAlmostEqual(items_by_symbol['USDT']['current_price'], 1.0, places=2)

    @patch.object(PriceService, 'get_top10_recommended_assets')
    @patch.object(PriceService, 'get_prices')
    def test_sort_order_portfolio_first(self, mock_get_prices, mock_top10):
        """Сортировка: сначала портфельные, затем ТОП-10, затем остальные."""
        mock_top10.return_value = MOCK_TOP10_ASSETS
        mock_get_prices.return_value = MOCK_PRICES

        result = PriceService().get_available_for_trade(['SHIB'])

        # Первый элемент — SHIB (in_portfolio=True)
        self.assertEqual(result[0]['symbol'], 'SHIB')
        self.assertTrue(result[0]['in_portfolio'])

        # Стейблкоины (USDT/USDC) идут после ТОП-10 (т.к. is_recommended=False, in_portfolio=False)
        non_portfolio = [r for r in result if not r['in_portfolio']]
        recommended_idx = [i for i, r in enumerate(non_portfolio) if r['is_recommended']]
        non_recommended_idx = [i for i, r in enumerate(non_portfolio) if not r['is_recommended']]
        if recommended_idx and non_recommended_idx:
            self.assertLess(max(recommended_idx), min(non_recommended_idx))


class TradableAssetsEndpointTests(TestCase):
    """GET /api/portfolio/tradable-assets/."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/tradable-assets/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    @patch('portfolios.views.PriceService')
    def test_endpoint_returns_assets(self, mock_class):
        """Endpoint возвращает список assets с метками."""
        mock_service = MagicMock()
        mock_service.get_available_for_trade.return_value = [
            {
                'symbol': 'BTC',
                'name': 'Bitcoin',
                'current_price': 100000.0,
                'is_recommended': True,
                'in_portfolio': True,
                'is_stable': False,
            },
            {
                'symbol': 'USDT',
                'name': 'Tether',
                'current_price': 1.0,
                'is_recommended': False,
                'in_portfolio': False,
                'is_stable': True,
            },
        ]
        mock_class.return_value = mock_service

        # Создаём активный портфель с BTC
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
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

        response = self.client.get(self.url, **self._headers())

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = response.json()
        self.assertEqual(data['count'], 2)
        symbols = [a['symbol'] for a in data['assets']]
        self.assertIn('BTC', symbols)
        self.assertIn('USDT', symbols)

        # Проверяем, что view передал в сервис символы текущего портфеля
        mock_service.get_available_for_trade.assert_called_once()
        args, _ = mock_service.get_available_for_trade.call_args
        self.assertIn('BTC', args[0])

    @patch('portfolios.views.PriceService')
    def test_endpoint_without_active_portfolio(self, mock_class):
        """Без активного портфеля — список всё равно возвращается (пустой портфельный список)."""
        mock_service = MagicMock()
        mock_service.get_available_for_trade.return_value = [
            {
                'symbol': 'BTC',
                'name': 'Bitcoin',
                'current_price': 100000.0,
                'is_recommended': True,
                'in_portfolio': False,
                'is_stable': False,
            },
        ]
        mock_class.return_value = mock_service

        response = self.client.get(self.url, **self._headers())

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        data = response.json()
        self.assertGreaterEqual(data['count'], 1)

        # В сервис передан пустой список символов
        args, _ = mock_service.get_available_for_trade.call_args
        self.assertEqual(args[0], [])
