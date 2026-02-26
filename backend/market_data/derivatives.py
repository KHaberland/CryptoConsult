"""
Интеграция с Binance Futures API — Funding Rate, Open Interest, Long/Short ratio.
Опционально: Coinglass API для ликвидаций (при наличии COINGLASS_API_KEY).
"""

import logging
import os
import time
import requests
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"
BINANCE_DATA = "https://fapi.binance.com/futures/data"
COINGLASS_URL = "https://open-api-v4.coinglass.com/api/futures/liquidation"


def _get_btc_price() -> float:
    """Получить текущую цену BTC с Binance."""
    try:
        r = requests.get(
            f"{BINANCE_FAPI}/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5
        )
        if r.ok:
            return float(r.json().get("price", 97000.0))
    except Exception:
        pass
    return 97000.0


def _get_long_short_ratio() -> Optional[Dict]:
    """
    Long/Short ratio — соотношение лонгов и шортов по всем аккаунтам.
    longAccount: доля аккаунтов с лонгами (0.66 = 66%)
    shortAccount: доля аккаунтов с шортами
    """
    try:
        r = requests.get(
            f"{BINANCE_DATA}/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        item = data[0]
        return {
            "long_short_ratio": float(item.get("longShortRatio", 1.0)),
            "long_account_pct": float(item.get("longAccount", 0.5)) * 100,
            "short_account_pct": float(item.get("shortAccount", 0.5)) * 100,
        }
    except Exception as e:
        logger.warning(f"Ошибка Long/Short ratio: {e}")
        return None


def _get_open_interest_history() -> Optional[Tuple[float, float]]:
    """
    Open Interest: текущий и 7 дней назад (для тренда).
    Returns (oi_now_usd, oi_7d_ago_usd) или None.
    """
    try:
        btc_price = _get_btc_price()
        # Текущий OI (в контрактах)
        r = requests.get(
            f"{BINANCE_FAPI}/openInterest",
            params={"symbol": "BTCUSDT"},
            timeout=10
        )
        r.raise_for_status()
        oi_now_contracts = float(r.json().get("openInterest", 0))
        oi_now_usd = oi_now_contracts * 0.1 * btc_price
        # OI 7 дней назад — openInterestHist возвращает sumOpenInterestValue в USD
        r_hist = requests.get(
            f"{BINANCE_DATA}/openInterestHist",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 168},
            timeout=10
        )
        r_hist.raise_for_status()
        hist = r_hist.json()
        if hist:
            last = hist[-1]
            if "sumOpenInterestValue" in last:
                oi_7d_ago_usd = float(last["sumOpenInterestValue"])
            else:
                oi_7d_ago_usd = float(last.get("sumOpenInterest", 0)) * 0.1 * btc_price
        else:
            oi_7d_ago_usd = oi_now_usd
        return (oi_now_usd, oi_7d_ago_usd)
    except Exception as e:
        logger.warning(f"Ошибка Open Interest history: {e}")
        return None


def _get_liquidations_7d() -> Optional[Dict]:
    """
    Ликвидации за 7 дней через Coinglass (требует COINGLASS_API_KEY).
    Returns: {"long_liquidations_usd": float, "short_liquidations_usd": float, "total_usd": float}
    """
    api_key = os.environ.get("COINGLASS_API_KEY")
    if not api_key:
        return None
    try:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - 7 * 24 * 60 * 60 * 1000
        r = requests.get(
            COINGLASS_URL,
            params={
                "exchange": "Binance",
                "symbol": "BTC",
                "min_liquidation_amount": "1000",
                "start_time": start_ms,
                "end_time": end_ms,
            },
            headers={"CG-API-KEY": api_key},
            timeout=15
        )
        if not r.ok:
            return None
        data = r.json()
        if data.get("code") != "0":
            return None
        items = data.get("data", [])
        long_liq = sum(item["usd_value"] for item in items if item.get("side") == 1)
        short_liq = sum(item["usd_value"] for item in items if item.get("side") == 2)
        return {
            "long_liquidations_usd": long_liq,
            "short_liquidations_usd": short_liq,
            "total_usd": long_liq + short_liq,
        }
    except Exception as e:
        logger.warning(f"Ошибка Coinglass liquidations: {e}")
        return None


def _interpret_derivatives(data: Dict) -> str:
    """
    Вывод: рынок перегружен лонгами / очищен / нейтральный.
    """
    funding = data.get("funding_rate", 0) or 0
    long_pct = data.get("long_account_pct", 50)
    liq = data.get("liquidations_7d")
    oi_change = data.get("open_interest_7d_change_pct")

    # Funding сильно положительный — лонги платят шортам, перегрев
    if funding > 0.0001:
        return "рынок перегружен лонгами"
    if funding < -0.00005:
        return "рынок перегружен шортами (контринтуитивно бычий)"

    # Long/Short: >60% лонгов — перегрев
    if long_pct > 60:
        return "рынок перегружен лонгами"
    if long_pct < 40:
        return "рынок перегружен шортами"

    # Массовые ликвидации лонгов — рынок очищен, бычий сигнал
    if liq and liq.get("long_liquidations_usd", 0) > 0:
        total = liq.get("total_usd", 0)
        if total > 100_000_000:  # >100M USD
            return "рынок очищен (массовые ликвидации)"

    # Рост OI на фоне падения — перегрев
    if oi_change and oi_change > 10:
        return "рынок перегружен (рост OI)"

    return "нейтральный баланс"


def get_btc_derivatives() -> Optional[Dict]:
    """
    Получить данные по деривативам BTC: Funding Rate, Open Interest, Long/Short, ликвидации.
    
    Returns:
        {
            "funding_rate": float,
            "funding_rate_8h_avg": float,
            "open_interest": float,
            "open_interest_usd": float,
            "open_interest_7d_ago_usd": float,
            "open_interest_7d_change_pct": float,
            "long_short_ratio": float,
            "long_account_pct": float,
            "short_account_pct": float,
            "liquidations_7d": {"long_liquidations_usd", "short_liquidations_usd", "total_usd"} | None,
            "interpretation": "рынок перегружен лонгами / очищен / нейтральный"
        } или None при ошибке
    """
    try:
        # Funding Rate
        fr_resp = requests.get(
            f"{BINANCE_FAPI}/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 3},
            timeout=10
        )
        fr_resp.raise_for_status()
        funding_data = fr_resp.json()
        rates = [float(r["fundingRate"]) for r in funding_data] if funding_data else []
        funding_rate = rates[0] if rates else 0.0
        funding_rate_8h_avg = sum(rates) / len(rates) if rates else 0.0

        # Open Interest + история
        oi_hist = _get_open_interest_history()
        btc_price = _get_btc_price()
        if oi_hist:
            oi_now_usd, oi_7d_ago_usd = oi_hist
            oi_change = (
                (oi_now_usd - oi_7d_ago_usd) / oi_7d_ago_usd * 100
                if oi_7d_ago_usd else 0
            )
        else:
            oi_resp = requests.get(
                f"{BINANCE_FAPI}/openInterest",
                params={"symbol": "BTCUSDT"},
                timeout=10
            )
            oi_resp.raise_for_status()
            oi = float(oi_resp.json().get("openInterest", 0))
            oi_now_usd = oi * 0.1 * btc_price
            oi_7d_ago_usd = oi_now_usd
            oi_change = 0.0

        # Long/Short
        ls = _get_long_short_ratio() or {}
        long_pct = ls.get("long_account_pct", 50)
        short_pct = ls.get("short_account_pct", 50)
        ls_ratio = ls.get("long_short_ratio", 1.0)

        # Ликвидации (опционально)
        liquidations = _get_liquidations_7d()

        result = {
            "funding_rate": funding_rate,
            "funding_rate_8h_avg": funding_rate_8h_avg,
            "open_interest": oi_now_usd / (btc_price * 0.1) if btc_price else 0,
            "open_interest_usd": oi_now_usd,
            "open_interest_7d_ago_usd": oi_7d_ago_usd,
            "open_interest_7d_change_pct": oi_change,
            "long_short_ratio": ls_ratio,
            "long_account_pct": long_pct,
            "short_account_pct": short_pct,
            "liquidations_7d": liquidations,
            "interpretation": "",
        }

        # Интерпретация
        result["interpretation"] = _interpret_derivatives(result)

        return result
    except Exception as e:
        logger.warning(f"Ошибка получения деривативов BTC: {e}")
        return None
