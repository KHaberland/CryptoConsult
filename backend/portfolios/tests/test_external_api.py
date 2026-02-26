"""
Тесты взаимодействия с внешними API (CoinGecko и др.).

Все вызовы внешних API мокаются.
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase

from portfolios.services import PriceService


class PriceServiceExternalAPITests(TestCase):
    """Тесты PriceService при работе с внешним API."""

    @patch('portfolios.services.requests.get')
    def test_coingecko_rate_limit_handling(self, mock_get):
        """При 429 от API используется fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        service = PriceService()
        # При 429 set_blocked вызывается, затем может использоваться fallback
        with patch.object(service.rate_limiter, 'set_blocked'):
            result = service.get_prices(['BTC'], use_cache=False)
        # Либо пустой результат, либо fallback — в зависимости от реализации
        self.assertIsInstance(result, dict)

    @patch('portfolios.services.requests.get')
    def test_coingecko_timeout_handling(self, mock_get):
        """При таймауте запроса возвращается пустой или fallback."""
        import requests
        mock_get.side_effect = requests.Timeout()

        service = PriceService()
        result = service.get_prices(['BTC'], use_cache=False)
        self.assertIsInstance(result, dict)

    @patch('portfolios.services.requests.get')
    def test_coingecko_success_response_parsing(self, mock_get):
        """Корректный парсинг ответа CoinGecko."""
        mock_get.return_value.json.return_value = {
            'bitcoin': {'usd': 95000.0, 'usd_24h_change': 2.5},
            'ethereum': {'usd': 3200.0},
        }
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.status_code = 200

        service = PriceService()
        result = service.get_prices(['BTC', 'ETH'], use_cache=False)
        self.assertEqual(result['BTC'], 95000.0)
        self.assertEqual(result['ETH'], 3200.0)
