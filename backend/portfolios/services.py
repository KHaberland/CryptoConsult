"""
Сервис для получения цен криптовалют.
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
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
    
    # Маппинг символов на ID CoinGecko (включая частые из топ-15 для портфеля новичка)
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
        "POL": "polygon-ecosystem-token",
        "AVAX": "avalanche-2",
        "LINK": "chainlink",
        "UNI": "uniswap",
        "ATOM": "cosmos",
        "LTC": "litecoin",
        "TRX": "tron",
        "SHIB": "shiba-inu",
        "BCH": "bitcoin-cash",
        "LEO": "leo-token",
        "HYPE": "hyperliquid",
        "USDE": "ethena-usde",
        "USDS": "usds",
        "CC": "canton-network",
        "XMR": "monero",
        "DAI": "dai",
        "STETH": "staked-ether",
        "WBTC": "wrapped-bitcoin",
    }
    
    # Обратный маппинг
    ID_TO_SYMBOL = {v: k for k, v in SYMBOL_TO_ID.items()}
    
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
        "POL": 0.5,
        "AVAX": 40.0,
        "LINK": 25.0,
        "UNI": 15.0,
        "ATOM": 10.0,
        "LTC": 130.0,
        "TRX": 0.25,
        "SHIB": 0.00003,
        "BCH": 500.0,
        "LEO": 8.0,
        "HYPE": 30.0,
        "USDE": 1.0,
        "USDS": 1.0,
        "CC": 0.16,
        "XMR": 320.0,
        "DAI": 1.0,
        "STETH": 3500.0,
        "WBTC": 100000.0,
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
    
    def get_historical_prices_with_volumes(
        self,
        symbol: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Получить исторические цены и объёмы актива (для анализа BTC).
        
        Returns:
            Список [{"date": timestamp, "price": float, "volume": float}, ...]
        """
        symbol = symbol.upper()
        if symbol not in self.SYMBOL_TO_ID:
            return []
        
        cache_key = f"history_vol:{symbol}:{days}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        self.rate_limiter.wait_if_needed()
        coin_id = self.SYMBOL_TO_ID[symbol]
        
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": days},
                timeout=15
            )
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            response.raise_for_status()
            data = response.json()
            
            prices_by_ts = {ts: p for ts, p in data.get("prices", [])}
            volumes_by_ts = {ts: v for ts, v in data.get("total_volumes", [])}
            
            result = []
            for ts in sorted(prices_by_ts.keys()):
                result.append({
                    "date": ts,
                    "price": prices_by_ts[ts],
                    "volume": volumes_by_ts.get(ts, 0),
                })
            if result:
                self.cache.set(cache_key, result)
            return result
        except requests.RequestException as e:
            logger.error(f"Ошибка получения истории {symbol}: {e}")
            stale = self.cache.get_stale(cache_key)
            return stale if stale else []
    
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

    @classmethod
    def get_stablecoin_symbols(cls) -> List[str]:
        """Стейблкоины, доступные для swap по умолчанию."""
        return ['USDT', 'USDC']

    def get_available_for_trade(self, portfolio_symbols: List[str]) -> List[Dict]:
        """
        Список монет, доступных для покупки/обмена в активном портфеле:
        union(текущие активы портфеля, ТОП-10, стейблкоины).

        Returns:
            Список словарей вида:
            {symbol, name, current_price, is_recommended, in_portfolio, is_stable}
        """
        top10 = self.get_top10_recommended_assets()
        top_map = {(c.get('symbol') or '').upper(): c for c in top10 if c.get('symbol')}
        portfolio_set = {(s or '').upper() for s in portfolio_symbols if s}
        stables = set(self.get_stablecoin_symbols())

        symbols = sorted(portfolio_set | set(top_map.keys()) | stables)

        # Подтягиваем цены пачкой одним запросом
        prices = self.get_prices(symbols)

        result: List[Dict] = []
        for sym in symbols:
            top_data = top_map.get(sym, {})
            name = top_data.get('name') or sym
            price = prices.get(sym)
            if price is None:
                price = top_data.get('current_price') or 0
                if sym in stables and not price:
                    price = 1.0
            result.append({
                'symbol': sym,
                'name': name,
                'current_price': float(price or 0),
                'is_recommended': sym in top_map,
                'in_portfolio': sym in portfolio_set,
                'is_stable': sym in stables,
            })

        # Сортировка: сначала текущие портфельные, затем ТОП-10, затем остальные
        result.sort(
            key=lambda x: (not x['in_portfolio'], not x['is_recommended'], x['symbol'])
        )
        return result

    # Стейблкойны по символу (CoinGecko)
    STABLECOIN_SYMBOLS = frozenset({
        "usdt", "usdc", "busd", "dai", "tusd", "usdd", "pyusd", "usds", "usde",
        "fdusd", "usdp", "frax", "gusd", "usdy", "usd1", "usdg", "usdf", "bfusd",
        "usdtb", "usd0", "usdai", "gho", "rlusd", "figr_heloc",
    })

    def fetch_top_coins_from_coingecko(self, per_page: int = 15) -> List[Dict]:
        """
        Получить топ монет по капитализации с CoinGecko.

        Returns:
            Список словарей: [{"symbol": "BTC", "name": "Bitcoin", "market_cap": ...}, ...]
        """
        cache_key = f"coingecko_top_{per_page}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Топ монет получен из кэша")
            return cached

        self.rate_limiter.wait_if_needed()
        try:
            response = requests.get(
                f"{self.COINGECKO_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": 1,
                    "sparkline": "false",
                },
                timeout=15,
            )
            if response.status_code == 429:
                self.rate_limiter.set_blocked(60)
                raise requests.RequestException("Rate limited (429)")
            response.raise_for_status()
            data = response.json()

            result = []
            for coin in data:
                symbol = (coin.get("symbol") or "").upper()
                name = coin.get("name") or symbol
                result.append({
                    "symbol": symbol,
                    "name": name,
                    "market_cap": coin.get("market_cap") or 0,
                    "current_price": coin.get("current_price") or 0,
                })
            if result:
                self.cache.set(cache_key, result)
            logger.info(f"CoinGecko: загружен топ-{len(result)} монет")
            return result
        except requests.RequestException as e:
            logger.error(f"Ошибка CoinGecko топ: {e}")
            stale = self.cache.get_stale(cache_key)
            if stale:
                return stale
            return []

    def get_top10_recommended_symbols(self) -> List[str]:
        """
        ТОП-10 ликвидных криптовалют для долгосрочного инвестирования
        (CoinGecko по капитализации, исключая стейблкоины).
        Используется для валидации импортируемого портфеля.
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top:
            return ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "DOT", "LINK"]

        result: List[str] = []
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if not sym:
                continue
            if (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
                continue
            result.append(sym)
            if len(result) >= 10:
                break
        return result[:10]

    def get_top10_recommended_assets(self) -> List[Dict]:
        """
        То же, что get_top10_recommended_symbols, но с расширенными данными
        (имя, цена, market_cap) для UI-выбора при импорте.
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top:
            return []
        result: List[Dict] = []
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if not sym:
                continue
            if (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
                continue
            result.append({
                "symbol": sym,
                "name": coin.get("name") or sym,
                "current_price": coin.get("current_price") or 0,
                "market_cap": coin.get("market_cap") or 0,
            })
            if len(result) >= 10:
                break
        return result

    def get_beginner_portfolio_assets(self) -> List[Dict]:
        """
        Портфель для новичка на основе топ-15 CoinGecko:
        BTC 50%, ETH 30%, Стейблкойны 10%, Альты (5 из топ-15 кроме BTC/ETH/стейблов) 10% (по 2% каждый).
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top:
            # Fallback на фиксированную структуру, если API недоступен
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 50.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 30.0},
                {"symbol": "USDT", "name": "Tether", "percentage": 10.0},
                {"symbol": "XRP", "name": "XRP", "percentage": 2.0},
                {"symbol": "BNB", "name": "BNB", "percentage": 2.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 2.0},
                {"symbol": "USDC", "name": "USD Coin", "percentage": 2.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 2.0},
            ]

        assets: List[Dict] = []
        btc_done = eth_done = stable_done = False
        alts: List[Dict] = []

        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            price = coin.get("current_price") or 0
            if sym == "BTC" and not btc_done:
                assets.append({"symbol": sym, "name": name, "percentage": 50.0, "initial_price": price})
                btc_done = True
            elif sym == "ETH" and not eth_done:
                assets.append({"symbol": sym, "name": name, "percentage": 30.0, "initial_price": price})
                eth_done = True
            elif (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS and not stable_done:
                assets.append({"symbol": sym, "name": name, "percentage": 10.0, "initial_price": price})
                stable_done = True
            else:
                # Альты: не BTC, не ETH, не стейблкойн
                if sym not in ("BTC", "ETH") and (coin.get("symbol") or "").lower() not in self.STABLECOIN_SYMBOLS:
                    alts.append({"symbol": sym, "name": name, "initial_price": price})

        # Ровно 5 альтов по 2%
        for alt in alts[:5]:
            assets.append({
                "symbol": alt["symbol"],
                "name": alt["name"],
                "percentage": 2.0,
                "initial_price": alt.get("initial_price"),
            })

        # Если стейбла не было в топ-15, добавляем USDT 10%
        if not stable_done:
            insert_idx = 2
            for i, a in enumerate(assets):
                if a.get("symbol") == "ETH":
                    insert_idx = i + 1
                    break
            assets.insert(insert_idx, {"symbol": "USDT", "name": "Tether", "percentage": 10.0, "initial_price": 1.0})

        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01:
            diff = 100.0 - total
            if assets:
                assets[-1]["percentage"] = round(assets[-1]["percentage"] + diff, 2)
        return assets

    def get_some_experience_portfolio_assets(self) -> List[Dict]:
        """
        Базовый портфель для уровня «Немного опыта» (уровень 2):
        BTC 50%, ETH 20%, USDT 10%, 5 альткойнов из top 10 CoinGecko (кроме BTC, ETH, USDT) по 4% каждый.
        """
        top = self.fetch_top_coins_from_coingecko(per_page=10)
        if not top:
            # Fallback: BNB, SOL, XRP, ADA, DOGE (топ-10 без BTC, ETH, USDT)
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 50.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 20.0},
                {"symbol": "USDT", "name": "Tether", "percentage": 10.0},
                {"symbol": "BNB", "name": "Binance Coin", "percentage": 4.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 4.0},
                {"symbol": "XRP", "name": "XRP", "percentage": 4.0},
                {"symbol": "ADA", "name": "Cardano", "percentage": 4.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 4.0},
            ]

        assets: List[Dict] = []
        btc_done = eth_done = stable_done = False
        alts: List[Dict] = []

        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            price = coin.get("current_price") or 0
            if sym == "BTC" and not btc_done:
                assets.append({"symbol": sym, "name": name, "percentage": 50.0, "initial_price": price})
                btc_done = True
            elif sym == "ETH" and not eth_done:
                assets.append({"symbol": sym, "name": name, "percentage": 20.0, "initial_price": price})
                eth_done = True
            elif (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS and not stable_done:
                assets.append({"symbol": sym, "name": name, "percentage": 10.0, "initial_price": price})
                stable_done = True
            else:
                if sym not in ("BTC", "ETH") and (coin.get("symbol") or "").lower() not in self.STABLECOIN_SYMBOLS:
                    alts.append({"symbol": sym, "name": name, "initial_price": price})

        # Ровно 5 альтов по 4%
        for alt in alts[:5]:
            assets.append({
                "symbol": alt["symbol"],
                "name": alt["name"],
                "percentage": 4.0,
                "initial_price": alt.get("initial_price"),
            })

        if not stable_done:
            insert_idx = 2
            for i, a in enumerate(assets):
                if a.get("symbol") == "ETH":
                    insert_idx = i + 1
                    break
            assets.insert(insert_idx, {"symbol": "USDT", "name": "Tether", "percentage": 10.0, "initial_price": 1.0})

        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01:
            diff = 100.0 - total
            if assets:
                assets[-1]["percentage"] = round(assets[-1]["percentage"] + diff, 2)
        return assets

    def _get_infrastructure_alts(self, total_pct: float, per_alt: float) -> List[Dict]:
        """
        Альты из топ-15 CoinGecko (инфраструктурные проекты), как в портфеле начинающего.
        total_pct — общая доля на альты, per_alt — доля на каждый из 5 альтов.
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        alts: List[Dict] = []
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            if sym not in ("BTC", "ETH") and (coin.get("symbol") or "").lower() not in self.STABLECOIN_SYMBOLS:
                alts.append({"symbol": sym, "name": name, "initial_price": coin.get("current_price") or 0})
        result = []
        for alt in alts[:5]:
            result.append({
                "symbol": alt["symbol"],
                "name": alt["name"],
                "percentage": per_alt,
                "initial_price": alt.get("initial_price"),
            })
        if result and abs(sum(a["percentage"] for a in result) - total_pct) > 0.01:
            diff = total_pct - sum(a["percentage"] for a in result)
            result[-1]["percentage"] = round(result[-1]["percentage"] + diff, 2)
        return result

    def get_medium_portfolio_with_liquidity(self) -> List[Dict]:
        """
        ВАРИАНТ 1: Средний опыт + нужна возможность частичного вывода.
        50% BTC, 25% ETH, 15% стейблкоины (USDT/USDC), 10% инфраструктура (как у начинающего).
        """
        alts = self._get_infrastructure_alts(10.0, 2.0)
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top or not alts:
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 50.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 25.0},
                {"symbol": "USDT", "name": "Tether", "percentage": 15.0},
                {"symbol": "BNB", "name": "BNB", "percentage": 2.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 2.0},
                {"symbol": "XRP", "name": "XRP", "percentage": 2.0},
                {"symbol": "ADA", "name": "Cardano", "percentage": 2.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 2.0},
            ]
        btc_price = eth_price = 0
        stable_sym, stable_name = "USDT", "Tether"
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if sym == "BTC":
                btc_price = coin.get("current_price") or 0
            elif sym == "ETH":
                eth_price = coin.get("current_price") or 0
            elif (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
                stable_sym, stable_name = sym, coin.get("name") or sym
                break
        assets = [
            {"symbol": "BTC", "name": "Bitcoin", "percentage": 50.0, "initial_price": btc_price},
            {"symbol": "ETH", "name": "Ethereum", "percentage": 25.0, "initial_price": eth_price},
            {"symbol": stable_sym, "name": stable_name, "percentage": 15.0, "initial_price": 1.0},
        ]
        assets.extend(alts)
        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01 and assets:
            assets[-1]["percentage"] = round(assets[-1]["percentage"] + (100.0 - total), 2)
        return assets

    def get_medium_portfolio_no_liquidity(self) -> List[Dict]:
        """
        ВАРИАНТ 2: Средний опыт + могу держать без вывода (жёсткий холд 5 лет).
        55% BTC, 30% ETH, 10% SOL, 5% инфраструктура (как у начинающего).
        """
        alts = self._get_infrastructure_alts(5.0, 1.0)
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top or not alts:
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 55.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 30.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 10.0},
                {"symbol": "BNB", "name": "BNB", "percentage": 1.0},
                {"symbol": "XRP", "name": "XRP", "percentage": 1.0},
                {"symbol": "ADA", "name": "Cardano", "percentage": 1.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 1.0},
                {"symbol": "DOT", "name": "Polkadot", "percentage": 1.0},
            ]
        btc_price = eth_price = sol_price = 0
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if sym == "BTC":
                btc_price = coin.get("current_price") or 0
            elif sym == "ETH":
                eth_price = coin.get("current_price") or 0
            elif sym == "SOL":
                sol_price = coin.get("current_price") or 0
        assets = [
            {"symbol": "BTC", "name": "Bitcoin", "percentage": 55.0, "initial_price": btc_price},
            {"symbol": "ETH", "name": "Ethereum", "percentage": 30.0, "initial_price": eth_price},
            {"symbol": "SOL", "name": "Solana", "percentage": 10.0, "initial_price": sol_price},
        ]
        assets.extend(alts)
        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01 and assets:
            assets[-1]["percentage"] = round(assets[-1]["percentage"] + (100.0 - total), 2)
        return assets

    def _get_speculative_alt(self) -> Optional[Dict]:
        """Спекулятивный компонент: DOGE или другой мем/трендовый из топ-15."""
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            if sym in ("DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF"):
                return {"symbol": sym, "name": name, "percentage": 5.0, "initial_price": coin.get("current_price") or 0}
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            if sym not in ("BTC", "ETH") and (coin.get("symbol") or "").lower() not in self.STABLECOIN_SYMBOLS:
                return {"symbol": sym, "name": name, "percentage": 5.0, "initial_price": coin.get("current_price") or 0}
        return {"symbol": "DOGE", "name": "Dogecoin", "percentage": 5.0, "initial_price": 0}

    def _get_experimental_alt(self, exclude: set) -> Optional[Dict]:
        """Экспериментальный сектор: 1 альт из топ-15, не входящий в exclude."""
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            name = coin.get("name") or sym
            if sym not in exclude and (coin.get("symbol") or "").lower() not in self.STABLECOIN_SYMBOLS:
                return {"symbol": sym, "name": name, "percentage": 3.0, "initial_price": coin.get("current_price") or 0}
        return None

    def get_advanced_portfolio_with_liquidity(self) -> List[Dict]:
        """
        Продвинутый инвестор ВАРИАНТ 1: с возможностью частичного вывода.
        45% BTC, 25% ETH, 10% стейбл, 10% SOL, 5% LINK, 5% спекулятивный (DOGE и т.п.).
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top:
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 45.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 25.0},
                {"symbol": "USDT", "name": "Tether", "percentage": 10.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 10.0},
                {"symbol": "LINK", "name": "Chainlink", "percentage": 5.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 5.0},
            ]
        btc_price = eth_price = sol_price = link_price = 0
        stable_sym, stable_name = "USDT", "Tether"
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if sym == "BTC":
                btc_price = coin.get("current_price") or 0
            elif sym == "ETH":
                eth_price = coin.get("current_price") or 0
            elif sym == "SOL":
                sol_price = coin.get("current_price") or 0
            elif sym == "LINK":
                link_price = coin.get("current_price") or 0
            elif (coin.get("symbol") or "").lower() in self.STABLECOIN_SYMBOLS:
                stable_sym, stable_name = sym, coin.get("name") or sym
        speculative = self._get_speculative_alt()
        assets = [
            {"symbol": "BTC", "name": "Bitcoin", "percentage": 45.0, "initial_price": btc_price},
            {"symbol": "ETH", "name": "Ethereum", "percentage": 25.0, "initial_price": eth_price},
            {"symbol": stable_sym, "name": stable_name, "percentage": 10.0, "initial_price": 1.0},
            {"symbol": "SOL", "name": "Solana", "percentage": 10.0, "initial_price": sol_price},
            {"symbol": "LINK", "name": "Chainlink", "percentage": 5.0, "initial_price": link_price},
        ]
        if speculative:
            assets.append(speculative)
        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01 and assets:
            assets[-1]["percentage"] = round(assets[-1]["percentage"] + (100.0 - total), 2)
        return assets

    def get_advanced_portfolio_no_liquidity(self) -> List[Dict]:
        """
        Продвинутый инвестор ВАРИАНТ 2: капитал не нужен 7 лет (жёсткий холд).
        40% BTC, 30% ETH, 15% SOL, 7% LINK, 5% DOGE, 3% экспериментальный.
        """
        top = self.fetch_top_coins_from_coingecko(per_page=15)
        if not top:
            return [
                {"symbol": "BTC", "name": "Bitcoin", "percentage": 40.0},
                {"symbol": "ETH", "name": "Ethereum", "percentage": 30.0},
                {"symbol": "SOL", "name": "Solana", "percentage": 15.0},
                {"symbol": "LINK", "name": "Chainlink", "percentage": 7.0},
                {"symbol": "DOGE", "name": "Dogecoin", "percentage": 5.0},
                {"symbol": "XRP", "name": "XRP", "percentage": 3.0},
            ]
        btc_price = eth_price = sol_price = link_price = doge_price = 0
        for coin in top:
            sym = (coin.get("symbol") or "").upper()
            if sym == "BTC":
                btc_price = coin.get("current_price") or 0
            elif sym == "ETH":
                eth_price = coin.get("current_price") or 0
            elif sym == "SOL":
                sol_price = coin.get("current_price") or 0
            elif sym == "LINK":
                link_price = coin.get("current_price") or 0
            elif sym == "DOGE":
                doge_price = coin.get("current_price") or 0
        speculative = self._get_speculative_alt()
        spec_sym = speculative.get("symbol") if speculative else ""
        experimental = self._get_experimental_alt(exclude={"BTC", "ETH", "SOL", "LINK", spec_sym})
        assets = [
            {"symbol": "BTC", "name": "Bitcoin", "percentage": 40.0, "initial_price": btc_price},
            {"symbol": "ETH", "name": "Ethereum", "percentage": 30.0, "initial_price": eth_price},
            {"symbol": "SOL", "name": "Solana", "percentage": 15.0, "initial_price": sol_price},
            {"symbol": "LINK", "name": "Chainlink", "percentage": 7.0, "initial_price": link_price},
        ]
        if speculative:
            if speculative.get("symbol") == "DOGE":
                speculative["initial_price"] = doge_price
            assets.append(speculative)
        if experimental:
            assets.append(experimental)
        total = sum(a["percentage"] for a in assets)
        if abs(total - 100.0) > 0.01 and assets:
            assets[-1]["percentage"] = round(assets[-1]["percentage"] + (100.0 - total), 2)
        return assets


def recompute_percentages_by_market(portfolio, prices: Dict[str, float]) -> None:
    """
    Пересчитать `PortfolioAsset.percentage` пропорционально текущей рыночной
    стоимости активов портфеля.

    Args:
        portfolio: экземпляр Portfolio.
        prices: словарь {symbol: current_price_usd}. Если цены для какого-то
            символа нет, используется initial_price актива.

    Если суммарная рыночная стоимость <= 0 — функция ничего не меняет.
    Остаточная погрешность округления записывается в последний актив,
    чтобы Σ percentage == 100.
    """
    assets = list(portfolio.assets.all())
    if not assets:
        return

    values: List[float] = []
    total = 0.0
    for asset in assets:
        units = float(asset.units or 0)
        price = prices.get(asset.symbol)
        if price is None or price <= 0:
            price = float(asset.initial_price or 0)
        v = units * float(price or 0)
        values.append(v)
        total += v

    if total <= 0:
        return

    for asset, v in zip(assets, values):
        asset.percentage = round(v / total * 100, 2)
        asset.save(update_fields=['percentage'])

    # Выравниваем округление, чтобы Σ percentage == 100
    refreshed = list(portfolio.assets.all())
    diff = 100.0 - sum(float(a.percentage or 0) for a in refreshed)
    if abs(diff) > 0.001 and refreshed:
        last = refreshed[-1]
        last.percentage = round(float(last.percentage or 0) + diff, 2)
        last.save(update_fields=['percentage'])


class WalletLedger:
    """Сервис управления балансами по кошелькам.

    Поддерживает инвариант:
        PortfolioAsset.units == Σ WalletHolding.units по всем кошелькам портфеля
        для данного symbol.

    Все вычисления выполняются в Decimal — без float, чтобы не терять точность
    при сложении/вычитании единиц активов (см. PLAN06-realization.md, Агент 7).
    """

    DEFAULT_WALLET_NAME = "Общий кошелёк"
    DEFAULT_WALLET_TYPE = "other"
    ZERO = Decimal("0")

    @staticmethod
    def _to_decimal(value) -> Decimal:
        """Привести значение к Decimal без потери точности."""
        if value is None:
            return WalletLedger.ZERO
        if isinstance(value, Decimal):
            return value
        # str(...) важен — иначе float конвертится с ошибкой представления.
        return Decimal(str(value))

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return (symbol or "").strip().upper()

    @classmethod
    def get_default_wallet(cls, portfolio):
        """Получить (или создать) default-кошелёк портфеля.

        Логика:
            1) если уже есть Wallet с is_default=True — возвращаем его;
            2) если есть Wallet с именем DEFAULT_WALLET_NAME — помечаем его
               как default и возвращаем;
            3) иначе создаём новый default Wallet.
        """
        from .models import Wallet

        wallet = Wallet.objects.filter(portfolio=portfolio, is_default=True).first()
        if wallet is not None:
            return wallet

        named = Wallet.objects.filter(
            portfolio=portfolio, name=cls.DEFAULT_WALLET_NAME
        ).first()
        if named is not None:
            named.is_default = True
            named.save(update_fields=["is_default", "updated_at"])
            return named

        return Wallet.objects.create(
            portfolio=portfolio,
            name=cls.DEFAULT_WALLET_NAME,
            type=cls.DEFAULT_WALLET_TYPE,
            is_default=True,
            note="",
        )

    @classmethod
    def get_or_create_holding(cls, wallet, symbol: str):
        """Получить или создать WalletHolding для пары (wallet, symbol)."""
        from .models import WalletHolding

        sym = cls._normalize_symbol(symbol)
        if not sym:
            raise ValueError("symbol обязателен")

        holding, _ = WalletHolding.objects.get_or_create(
            wallet=wallet,
            symbol=sym,
            defaults={"units": cls.ZERO},
        )
        return holding

    @classmethod
    def add_units(cls, wallet, symbol: str, delta) -> "WalletHolding":  # type: ignore[name-defined]
        """Добавить delta к WalletHolding.units (delta может быть отрицательной).

        Бросает ValueError, если итоговый баланс уходит в минус.
        Возвращает обновлённый WalletHolding.
        """
        delta_dec = cls._to_decimal(delta)
        holding = cls.get_or_create_holding(wallet, symbol)
        current = cls._to_decimal(holding.units)
        new_value = current + delta_dec

        if new_value < cls.ZERO:
            raise ValueError(
                f"Недостаточно баланса {cls._normalize_symbol(symbol)} "
                f"на кошельке '{wallet.name}': есть {current}, требуется {-delta_dec}"
            )

        holding.units = new_value
        holding.save(update_fields=["units", "updated_at"])
        return holding

    @classmethod
    def aggregate_units(cls, portfolio, symbol: str) -> Decimal:
        """Σ WalletHolding.units по всем кошелькам портфеля для symbol."""
        from django.db.models import Sum
        from .models import WalletHolding

        sym = cls._normalize_symbol(symbol)
        if not sym:
            return cls.ZERO

        total = WalletHolding.objects.filter(
            wallet__portfolio=portfolio, symbol=sym
        ).aggregate(total=Sum("units"))["total"]

        return cls._to_decimal(total)

    @classmethod
    def sync_aggregate(cls, portfolio, symbol: str):
        """Обновить PortfolioAsset.units суммой WalletHolding.units.

        Возвращает обновлённый PortfolioAsset или None, если такого актива нет.
        """
        from .models import PortfolioAsset

        sym = cls._normalize_symbol(symbol)
        if not sym:
            return None

        total = cls.aggregate_units(portfolio, sym)

        asset = PortfolioAsset.objects.filter(
            portfolio=portfolio, symbol=sym
        ).first()
        if asset is None:
            return None

        asset.units = total
        asset.save(update_fields=["units"])
        return asset

    @classmethod
    def sync_all(cls, portfolio) -> int:
        """Синхронизировать units всех PortfolioAsset портфеля по WalletHolding.

        Возвращает количество обновлённых активов.
        """
        updated = 0
        for asset in portfolio.assets.all():
            if cls.sync_aggregate(portfolio, asset.symbol) is not None:
                updated += 1
        return updated

    @classmethod
    def ensure_consistent_holdings(cls, portfolio):
        """Лениво заполнить WalletHolding для портфелей, у которых сумма
        WalletHolding.units меньше PortfolioAsset.units.

        Зачем нужно:
            * портфели, созданные до миграции 0008 (или в тестах в обход
              миграции), имеют PortfolioAsset.units > 0, но Σ WalletHolding.units
              может быть равна 0;
            * перед любой операцией над балансами через WalletLedger нужно
              привести систему к консистентному состоянию, иначе sync_aggregate
              "обнулит" исторические остатки.

        Логика:
            * для каждого PortfolioAsset считаем aggregate = Σ WalletHolding.units;
            * если aggregate < asset.units — добавляем разницу в default-кошелёк;
            * если aggregate >= asset.units — ничего не делаем (уже синхронно
              или избыток на стороне кошельков, который сам исправит
              sync_aggregate в дальнейшем).

        Идемпотентно: повторный вызов — no-op.

        Возвращает default Wallet (создаст при необходимости).
        """
        default_wallet = cls.get_default_wallet(portfolio)
        for asset in portfolio.assets.all():
            sym = cls._normalize_symbol(asset.symbol)
            if not sym:
                continue
            aggregate = cls.aggregate_units(portfolio, sym)
            asset_units = cls._to_decimal(asset.units)
            if aggregate < asset_units:
                diff = asset_units - aggregate
                cls.add_units(default_wallet, sym, diff)
        return default_wallet
