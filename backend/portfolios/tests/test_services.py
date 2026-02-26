"""
Тесты сервисов портфеля (PriceService, PriceCache и др.).
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase

from portfolios.services import PriceCache, PriceService


class PriceCacheTests(TestCase):
    """Тесты кэша цен."""

    def test_cache_set_and_get(self):
        """Сохранение и получение из кэша."""
        cache = PriceCache(ttl_seconds=300)
        cache.set('key1', {'BTC': 100000.0})
        result = cache.get('key1')
        self.assertEqual(result, {'BTC': 100000.0})

    def test_cache_clear(self):
        """Очистка кэша."""
        cache = PriceCache(ttl_seconds=300)
        cache.set('key1', {'data': 1})
        cache.clear()
        self.assertIsNone(cache.get('key1'))

    def test_get_stale_returns_expired_data(self):
        """get_stale возвращает данные даже после истечения TTL."""
        cache = PriceCache(ttl_seconds=0)  # TTL = 0 для быстрого истечения
        cache.set('key1', {'BTC': 50000.0})
        # get может вернуть None из-за TTL, get_stale — всегда данные
        stale = cache.get_stale('key1')
        self.assertEqual(stale, {'BTC': 50000.0})


class PriceServiceTests(TestCase):
    """Тесты PriceService (с моками внешнего API)."""

    def test_symbol_to_id_mapping(self):
        """Маппинг символов на ID CoinGecko."""
        service = PriceService()
        self.assertEqual(service.SYMBOL_TO_ID['BTC'], 'bitcoin')
        self.assertEqual(service.SYMBOL_TO_ID['ETH'], 'ethereum')

    def test_fallback_prices_exist(self):
        """Fallback-цены заданы для основных активов."""
        service = PriceService()
        self.assertIn('BTC', service.FALLBACK_PRICES)
        self.assertIn('ETH', service.FALLBACK_PRICES)
        self.assertGreater(service.FALLBACK_PRICES['BTC'], 0)

    @patch('portfolios.services.requests.get')
    def test_get_prices_returns_dict(self, mock_get):
        """get_prices возвращает словарь цен."""
        mock_get.return_value.json.return_value = {
            'bitcoin': {'usd': 100000.0},
            'ethereum': {'usd': 3500.0},
        }
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.status_code = 200

        service = PriceService()
        result = service.get_prices(['BTC', 'ETH'], use_cache=False)
        self.assertIn('BTC', result)
        self.assertIn('ETH', result)
        self.assertEqual(result['BTC'], 100000.0)
