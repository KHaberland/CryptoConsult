"""
Сервис для получения цен криптовалют.
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import threading
import time

logger = logging.getLogger(__name__)


class PriceCache:
    """Простой кэш цен в памяти с TTL."""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Dict]:
        """Получить значение из кэша."""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if datetime.now() - entry['timestamp'] < self.ttl:
                    return entry['data']
                # Не удаляем устаревшие данные - они могут понадобиться как fallback
            return None
    
    def get_stale(self, key: str) -> Optional[Dict]:
        """Получить значение из кэша даже если TTL истёк (для fallback)."""
        with self._lock:
            if key in self._cache:
                return self._cache[key]['data']
            return None
    
    def set(self, key: str, data: Dict):
        """Сохранить значение в кэш."""
        with self._lock:
            self._cache[key] = {
                'data': data,
                'timestamp': datetime.now()
            }
    
    def clear(self):
        """Очистить кэш."""
        with self._lock:
            self._cache.clear()


# Глобальный экземпляр кэша (TTL = 5 минут для защиты от rate-limit)
price_cache = PriceCache(ttl_seconds=300)

# Глобальный rate limiter
class RateLimiter:
    """Простой rate limiter для защиты от блокировки API."""
    
    def __init__(self, min_interval_seconds: float = 3.0):
        self._last_request = datetime.min
        self._lock = threading.Lock()
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self._blocked_until: Optional[datetime] = None
    
    def wait_if_needed(self):
        """Ждать если нужно соблюсти rate limit."""
        with self._lock:
            now = datetime.now()
            
            # Проверяем, не заблокированы ли мы
            if self._blocked_until and now < self._blocked_until:
                wait_time = (self._blocked_until - now).total_seconds()
                logger.warning(f"Rate limited, ждём {wait_time:.1f} секунд")
                time.sleep(wait_time)
                now = datetime.now()
            
            # Соблюдаем минимальный интервал между запросами
            elapsed = now - self._last_request
            if elapsed < self.min_interval:
                wait_time = (self.min_interval - elapsed).total_seconds()
                time.sleep(wait_time)
            
            self._last_request = datetime.now()
    
    def set_blocked(self, seconds: int = 60):
        """Установить блокировку после получения 429."""
        with self._lock:
            self._blocked_until = datetime.now() + timedelta(seconds=seconds)
            logger.warning(f"API заблокировал нас, ждём {seconds} секунд")

# Глобальный rate limiter (минимум 3 секунды между запросами)
rate_limiter = RateLimiter(min_interval_seconds=3.0)


class PriceService:
    """Сервис для получения цен криптовалют через CoinGecko API."""
    
    COINGECKO_URL = "https://api.coingecko.com/api/v3"
    
    # Маппинг символов на ID CoinGecko
    SYMBOL_TO_ID = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BNB": "binancecoin",
        "SOL": "solana",
        "USDT": "tether",
        "USDC": "usd-coin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "MATIC": "matic-network",
        "AVAX": "avalanche-2",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "ATOM": "cosmos",
        "LTC": "litecoin",
        "TRX": "tron",
        "SHIB": "shiba-inu",
    }
    
    # Обратный маппинг
    ID_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_ID.items()}
    
    # Запасные цены (обновляются при успешных запросах)
    # Используются когда API недоступен
    FALLBACK_PRICES = {
        "BTC": 100000.0,
        "ETH": 3500.0,
        "BNB": 700.0,
        "SOL": 250.0,
        "USDT": 1.0,
        "USDC": 1.0,
        "XRP": 3.0,
        "ADA": 1.0,
        "DOGE": 0.4,
        "DOT": 8.0,
        "MATIC": 0.5,
        "AVAX": 40.0,
        "LINK": 25.0,
        "UNI": 15.0,
        "ATOM": 10.0,
        "LTC": 130.0,
        "TRX": 0.25,
        "SHIB": 0.00003,
    }
    
    def __init__(self):
        self.cache = price_cache
        self.rate_limiter = rate_limiter
    
    def get_prices(self, symbols: List[str], use_cache: bool = True) -> Dict[str, float]:
        """
        Получить текущие цены активов в USD.
        
        Args:
            symbols: Список символов криптовалют (BTC, ETH, ...)
            use_cache: Использовать кэш (по умолчанию True)
            
        Returns:
            Словарь {символ: цена_в_USD}
        """
        # Фильтруем только известные символы
        known_symbols = [s.upper() for s in symbols if s.upper() in self.SYMBOL_TO_ID]
        if not known_symbols:
            return {}
        
        # Создаём ключ кэша
        cache_key = "prices:" + ",".join(sorted(known_symbols))
        
        # Проверяем кэш (приоритет - свежие данные)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Цены получены из кэша: {cache_key}")
                return cached
        
        # Соблюдаем rate limit
        self.rate_limiter.wait_if_needed()
        
        # Конвертируем в ID для CoinGecko
        ids = [self.SYMBOL_TO_ID[s] for s in known_symbols]
        ids_str = ",".join(ids)
        
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/simple/price",
                params={
                    "ids": ids_str,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                },
                timeout=10
            )
            
            # Обработка rate limit
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            
            response.raise_for_status()
            data = response.json()
            
            # Конвертируем обратно в символы
            result = {}
            for coin_id, price_data in data.items():
                symbol = self.ID_TO_SYMBOL.get(coin_id)
                if symbol and "usd" in price_data:
                    result[symbol] = price_data["usd"]
            
            # Для стейблкоинов устанавливаем цену $1 если нет данных
            for symbol in known_symbols:
                if symbol in ("USDT", "USDC") and symbol not in result:
                    result[symbol] = 1.0
            
            # Сохраняем в кэш
            if use_cache and result:
                self.cache.set(cache_key, result)
            
            logger.info(f"Цены успешно получены от CoinGecko: {list(result.keys())}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Ошибка получения цен: {e}")
            
            # Пробуем вернуть кэшированные данные (даже устаревшие)
            stale_cached = self.cache.get_stale(cache_key)
            if stale_cached:
                logger.warning("Возвращаем устаревшие данные из кэша")
                return stale_cached
            
            # Возвращаем fallback цены
            logger.warning("Возвращаем запасные цены (fallback)")
            return {s: self.FALLBACK_PRICES.get(s, 0) for s in known_symbols}
    
    def get_prices_with_changes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Получить цены с изменениями за 24 часа.
        
        Args:
            symbols: Список символов криптовалют
            
        Returns:
            Словарь {символ: {"price": float, "change_24h": float}}
        """
        known_symbols = [s.upper() for s in symbols if s.upper() in self.SYMBOL_TO_ID]
        if not known_symbols:
            return {}
        
        # Создаём ключ кэша
        cache_key = "prices_changes:" + ",".join(sorted(known_symbols))
        
        # Проверяем кэш
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Цены с изменениями получены из кэша")
            return cached
        
        # Соблюдаем rate limit
        self.rate_limiter.wait_if_needed()
        
        ids = [self.SYMBOL_TO_ID[s] for s in known_symbols]
        ids_str = ",".join(ids)
        
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/simple/price",
                params={
                    "ids": ids_str,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                },
                timeout=10
            )
            
            # Обработка rate limit
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            
            response.raise_for_status()
            data = response.json()
            
            result = {}
            for coin_id, price_data in data.items():
                symbol = self.ID_TO_SYMBOL.get(coin_id)
                if symbol:
                    result[symbol] = {
                        "price": price_data.get("usd", 0),
                        "change_24h": price_data.get("usd_24h_change", 0)
                    }
            
            # Стейблкоины
            for symbol in known_symbols:
                if symbol in ("USDT", "USDC") and symbol not in result:
                    result[symbol] = {"price": 1.0, "change_24h": 0.0}
            
            # Сохраняем в кэш
            if result:
                self.cache.set(cache_key, result)
            
            logger.info(f"Цены с изменениями успешно получены от CoinGecko")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Ошибка получения цен с изменениями: {e}")
            
            # Пробуем вернуть кэшированные данные (даже устаревшие)
            stale_cached = self.cache.get_stale(cache_key)
            if stale_cached:
                logger.warning("Возвращаем устаревшие данные из кэша")
                return stale_cached
            
            # Возвращаем fallback цены
            logger.warning("Возвращаем запасные цены (fallback)")
            return {
                s: {"price": self.FALLBACK_PRICES.get(s, 0), "change_24h": 0.0}
                for s in known_symbols
            }
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Получить цену одного актива.
        
        Args:
            symbol: Символ криптовалюты
            
        Returns:
            Цена в USD или None
        """
        prices = self.get_prices([symbol])
        return prices.get(symbol.upper())
    
    def get_all_supported_prices(self) -> Dict[str, float]:
        """Получить цены всех поддерживаемых криптовалют."""
        return self.get_prices(list(self.SYMBOL_TO_ID.keys()))
    
    def get_historical_prices(
        self,
        symbol: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Получить исторические цены актива.
        
        Args:
            symbol: Символ криптовалюты
            days: Количество дней истории
            
        Returns:
            Список [{"date": timestamp, "price": float}, ...]
        """
        symbol = symbol.upper()
        if symbol not in self.SYMBOL_TO_ID:
            return []
        
        # Создаём ключ кэша
        cache_key = f"history:{symbol}:{days}"
        
        # Проверяем кэш (для исторических данных TTL можно увеличить)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Исторические цены {symbol} получены из кэша")
            return cached
        
        # Соблюдаем rate limit
        self.rate_limiter.wait_if_needed()
        
        coin_id = self.SYMBOL_TO_ID[symbol]
        
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/coins/{coin_id}/market_chart",
                params={
                    "vs_currency": "usd",
                    "days": days
                },
                timeout=15
            )
            
            # Обработка rate limit
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            
            response.raise_for_status()
            data = response.json()
            
            prices = []
            for timestamp, price in data.get("prices", []):
                prices.append({
                    "date": timestamp,
                    "price": price
                })
            
            # Сохраняем в кэш
            if prices:
                self.cache.set(cache_key, prices)
            
            return prices
            
        except requests.RequestException as e:
            logger.error(f"Ошибка получения исторических цен: {e}")
            
            # Пробуем вернуть кэшированные данные (даже устаревшие)
            stale_cached = self.cache.get_stale(cache_key)
            if stale_cached:
                logger.warning(f"Возвращаем устаревшие исторические данные {symbol} из кэша")
                return stale_cached
            
            return []
    
    def get_market_data(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Получить расширенные рыночные данные.
        
        Args:
            symbols: Список символов криптовалют
            
        Returns:
            Словарь с рыночными данными для каждого актива
        """
        known_symbols = [s.upper() for s in symbols if s.upper() in self.SYMBOL_TO_ID]
        if not known_symbols:
            return {}
        
        # Создаём ключ кэша
        cache_key = "market:" + ",".join(sorted(known_symbols))
        
        # Проверяем кэш
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug(f"Рыночные данные получены из кэша")
            return cached
        
        # Соблюдаем rate limit
        self.rate_limiter.wait_if_needed()
        
        ids = [self.SYMBOL_TO_ID[s] for s in known_symbols]
        ids_str = ",".join(ids)
        
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/coins/markets",
                params={
                    "ids": ids_str,
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "sparkline": "false",
                    "price_change_percentage": "24h,7d,30d"
                },
                timeout=15
            )
            
            # Обработка rate limit
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            
            response.raise_for_status()
            data = response.json()
            
            result = {}
            for coin in data:
                symbol = self.ID_TO_SYMBOL.get(coin.get("id"))
                if symbol:
                    result[symbol] = {
                        "price": coin.get("current_price", 0),
                        "market_cap": coin.get("market_cap", 0),
                        "volume_24h": coin.get("total_volume", 0),
                        "change_24h": coin.get("price_change_percentage_24h", 0),
                        "change_7d": coin.get("price_change_percentage_7d_in_currency", 0),
                        "change_30d": coin.get("price_change_percentage_30d_in_currency", 0),
                        "high_24h": coin.get("high_24h", 0),
                        "low_24h": coin.get("low_24h", 0),
                        "ath": coin.get("ath", 0),
                        "ath_change_percentage": coin.get("ath_change_percentage", 0),
                    }
            
            # Сохраняем в кэш
            if result:
                self.cache.set(cache_key, result)
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Ошибка получения рыночных данных: {e}")
            
            # Пробуем вернуть кэшированные данные (даже устаревшие)
            stale_cached = self.cache.get_stale(cache_key)
            if stale_cached:
                logger.warning("Возвращаем устаревшие рыночные данные из кэша")
                return stale_cached
            
            # Возвращаем базовые данные
            return {
                s: {
                    "price": self.FALLBACK_PRICES.get(s, 0),
                    "market_cap": 0,
                    "volume_24h": 0,
                    "change_24h": 0,
                    "change_7d": 0,
                    "change_30d": 0,
                    "high_24h": 0,
                    "low_24h": 0,
                    "ath": 0,
                    "ath_change_percentage": 0,
                }
                for s in known_symbols
            }
    
    @classmethod
    def get_supported_symbols(cls) -> List[str]:
        """Получить список поддерживаемых символов."""
        return list(cls.SYMBOL_TO_ID.keys())
    
    @classmethod
    def is_symbol_supported(cls, symbol: str) -> bool:
        """Проверить, поддерживается ли символ."""
        return symbol.upper() in cls.SYMBOL_TO_ID
