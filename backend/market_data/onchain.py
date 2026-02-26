"""
Он-чейн аналитика Bitcoin: Active addresses, Exchange flow, MVRV, SOPR, LTH.
Бесплатно: Blockchain.com API.
Опционально: Glassnode API (при наличии GLASSNODE_API_KEY).
"""

import logging
import os
import time
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

BLOCKCHAIN_STATS = "https://api.blockchain.info/stats"
BLOCKCHAIN_CHARTS = "https://api.blockchain.info/charts"
GLASSNODE_URL = "https://api.glassnode.com/v1/metrics"


def _get_blockchain_stats() -> Optional[Dict]:
    """Blockchain.com stats — бесплатно, без ключа."""
    try:
        r = requests.get(BLOCKCHAIN_STATS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"Ошибка Blockchain.com stats: {e}")
        return None


def _get_blockchain_chart(chart_name: str, days: int = 30) -> Optional[list]:
    """Blockchain.com charts — n-unique-addresses, n-transactions и др."""
    try:
        r = requests.get(
            f"{BLOCKCHAIN_CHARTS}/{chart_name}",
            params={"timespan": f"{days}days", "format": "json"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data.get("values", [])
    except Exception as e:
        logger.warning(f"Ошибка Blockchain.com chart {chart_name}: {e}")
        return None


def _get_glassnode_metric(
    endpoint: str,
    asset: str = "BTC",
    interval: str = "24h",
    days: int = 30
) -> Optional[Any]:
    """Запрос метрики Glassnode. Требует GLASSNODE_API_KEY."""
    api_key = os.environ.get("GLASSNODE_API_KEY")
    if not api_key:
        return None
    try:
        until = int(time.time())
        since = until - days * 24 * 3600
        r = requests.get(
            f"{GLASSNODE_URL}/{endpoint}",
            params={
                "a": asset,
                "s": since,
                "u": until,
                "i": interval,
                "api_key": api_key,
            },
            timeout=15
        )
        if not r.ok:
            return None
        data = r.json()
        if isinstance(data, list) and data:
            return data[-1].get("v", data[-1])
        return data
    except Exception as e:
        logger.warning(f"Ошибка Glassnode {endpoint}: {e}")
        return None


def _interpret_onchain(data: Dict) -> str:
    """
    Вывод: накопление / распределение / фаза капитуляции.
    """
    sopr = data.get("sopr")
    mvrv = data.get("mvrv")
    exchange_flow_signal = data.get("exchange_flow_signal", 0)
    lth_signal = data.get("lth_signal", 0)

    # SOPR < 1 — продажа в убыток, часто близко к дну (капитуляция)
    if sopr is not None and sopr < 0.95:
        return "фаза капитуляции (SOPR < 1)"
    if sopr is not None and sopr > 1.05:
        return "распределение (прибыльные продажи)"

    # Exchange flow: отток с бирж = накопление
    if exchange_flow_signal > 0:
        return "накопление (отток с бирж)"
    if exchange_flow_signal < 0:
        return "распределение (приток на биржи)"

    # MVRV > 3 — переоценка, риск коррекции
    if mvrv is not None and mvrv > 3.0:
        return "распределение (MVRV высокий)"
    if mvrv is not None and mvrv < 1.0:
        return "накопление (MVRV < 1, недооценка)"

    # Рост LTH — накопление
    if lth_signal > 0:
        return "накопление (рост LTH)"

    return "нейтральная фаза"


def get_btc_onchain() -> Optional[Dict]:
    """
    Получить он-чейн метрики Bitcoin.
    
    Returns:
        {
            "active_addresses": int,
            "active_addresses_7d_avg": float,
            "transactions_24h": int,
            "transactions_7d_avg": float,
            "mvrv": float | None,
            "sopr": float | None,
            "exchange_inflow_btc": float | None,
            "exchange_outflow_btc": float | None,
            "lth_supply_pct": float | None,
            "exchange_flow_signal": int,  # -1 приток, 0 нейтр, +1 отток
            "lth_signal": int,
            "sopr_signal": int,
            "interpretation": str
        } или None при критической ошибке
    """
    result: Dict[str, Any] = {
        "active_addresses": 0,
        "active_addresses_7d_avg": 0.0,
        "transactions_24h": 0,
        "transactions_7d_avg": 0.0,
        "mvrv": None,
        "sopr": None,
        "exchange_inflow_btc": None,
        "exchange_outflow_btc": None,
        "lth_supply_pct": None,
        "exchange_flow_signal": 0,
        "lth_signal": 0,
        "sopr_signal": 0,
        "interpretation": "нет данных",
    }

    # Blockchain.com — бесплатно
    stats = _get_blockchain_stats()
    if stats:
        result["transactions_24h"] = int(stats.get("n_tx", 0))
        result["transactions_7d_avg"] = result["transactions_24h"]  # упрощённо

    addr_data = _get_blockchain_chart("n-unique-addresses", 30)
    if addr_data:
        result["active_addresses"] = int(addr_data[-1]["y"]) if addr_data else 0
        last_7 = [v["y"] for v in addr_data[-7:]] if len(addr_data) >= 7 else [addr_data[-1]["y"]]
        result["active_addresses_7d_avg"] = sum(last_7) / len(last_7) if last_7 else 0

    tx_data = _get_blockchain_chart("n-transactions", 7)
    if tx_data:
        result["transactions_7d_avg"] = sum(v["y"] for v in tx_data) / len(tx_data) if tx_data else 0

    # Glassnode — опционально
    api_key = os.environ.get("GLASSNODE_API_KEY")
    if api_key:
        mvrv = _get_glassnode_metric("market/mvrv", days=7)
        if mvrv is not None:
            result["mvrv"] = float(mvrv) if not isinstance(mvrv, dict) else float(mvrv.get("v", 0))

        sopr = _get_glassnode_metric("indicators/sopr", days=7)
        if sopr is not None:
            val = float(sopr) if not isinstance(sopr, dict) else float(sopr.get("v", 1.0))
            result["sopr"] = val
            result["sopr_signal"] = 1 if val < 1.0 else (-1 if val > 1.05 else 0)

        # Exchange flow: transfers_volume_to_exchanges vs from
        inflow = _get_glassnode_metric("transactions/transfers_volume_to_exchanges_sum", days=7)
        outflow = _get_glassnode_metric("transactions/transfers_volume_from_exchanges_sum", days=7)
        if inflow is not None and outflow is not None:
            in_val = float(inflow) if not isinstance(inflow, dict) else 0
            out_val = float(outflow) if not isinstance(outflow, dict) else 0
            result["exchange_inflow_btc"] = in_val
            result["exchange_outflow_btc"] = out_val
            if out_val > in_val * 1.1:
                result["exchange_flow_signal"] = 1
            elif in_val > out_val * 1.1:
                result["exchange_flow_signal"] = -1

        # LTH supply
        lth = _get_glassnode_metric("supply/lth_supply_relative", days=7)
        if lth is not None:
            val = float(lth) if not isinstance(lth, dict) else 0
            result["lth_supply_pct"] = val * 100 if val <= 1 else val
            result["lth_signal"] = 1 if val > 0.65 else 0

    result["interpretation"] = _interpret_onchain(result)
    return result
