"""
Макроэкономика и ликвидность: ФРС, DXY, доходности, корреляция с S&P 500.
Опционально: FRED API (при наличии FRED_API_KEY).
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
# FRED series IDs
SERIES_FEDFUNDS = "FEDFUNDS"      # Federal Funds Effective Rate
SERIES_DGS10 = "DGS10"            # 10-Year Treasury Constant Maturity
SERIES_DTWEXBGS = "DTWEXBGS"     # Trade Weighted U.S. Dollar Index (Broad)
SERIES_SP500 = "SP500"            # S&P 500 Index


def _get_fred_observations(
    series_id: str,
    limit: int = 10,
    sort_order: str = "desc"
) -> Optional[List[Dict]]:
    """Получить последние наблюдения из FRED."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return None
    try:
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FRED_BASE}/series/observations",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
                "sort_order": sort_order,
                "limit": limit,
            },
            timeout=15
        )
        if not r.ok:
            try:
                err_body = r.json()
                logger.warning(f"FRED API {series_id}: HTTP {r.status_code} — {err_body.get('error_message', r.text[:200])}")
            except Exception:
                logger.warning(f"FRED API {series_id}: HTTP {r.status_code} — {r.text[:200]}")
            return None
        data = r.json()
        obs = data.get("observations", [])
        return obs
    except Exception as e:
        logger.warning(f"Ошибка FRED {series_id}: {e}")
        return None


def _parse_fred_value(obs: Dict) -> Optional[float]:
    """Извлечь числовое значение из наблюдения FRED."""
    val = obs.get("value")
    if val is None or val == ".":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_latest_fred(series_id: str) -> Optional[float]:
    """Получить последнее значение серии FRED."""
    obs = _get_fred_observations(series_id, limit=1)
    if not obs:
        return None
    return _parse_fred_value(obs[0])


def _get_fred_series_for_correlation(series_id: str, days: int = 30) -> Optional[List[float]]:
    """Получить серию цен за последние days дней (для расчёта корреляции)."""
    obs = _get_fred_observations(series_id, limit=days * 2, sort_order="desc")
    if not obs:
        return None
    values = []
    for o in obs:
        v = _parse_fred_value(o)
        if v is not None:
            values.append(v)
    return list(reversed(values)) if values else None


def _compute_correlation(btc_returns: List[float], sp_returns: List[float]) -> Optional[float]:
    """Корреляция Пирсона между двумя рядами доходностей."""
    if len(btc_returns) < 5 or len(sp_returns) < 5 or len(btc_returns) != len(sp_returns):
        return None
    n = len(btc_returns)
    mean_btc = sum(btc_returns) / n
    mean_sp = sum(sp_returns) / n
    cov = sum((b - mean_btc) * (s - mean_sp) for b, s in zip(btc_returns, sp_returns)) / n
    var_btc = sum((b - mean_btc) ** 2 for b in btc_returns) / n
    var_sp = sum((s - mean_sp) ** 2 for s in sp_returns) / n
    if var_btc <= 0 or var_sp <= 0:
        return None
    return cov / (var_btc ** 0.5 * var_sp ** 0.5)


def _interpret_macro(data: Dict) -> Tuple[int, str]:
    """
    macro_signal: -1 = сжатие, 0 = нейтрально, +1 = расширение
    interpretation: текстовое описание
    """
    fed = data.get("fed_funds_rate")
    dxy = data.get("dxy")
    dxy_change = data.get("dxy_30d_change_pct")
    treasury_10y = data.get("treasury_10y")
    sp_btc_corr = data.get("sp500_btc_correlation")

    score = 0
    parts = []

    # ФРС: снижение ставки = расширение (+1), рост = сжатие (-1)
    if fed is not None:
        if fed < 4.0:
            score += 1
            parts.append("ФРС смягчает (низкая ставка)")
        elif fed > 5.0:
            score -= 1
            parts.append("ФРС ужесточает (высокая ставка)")

    # DXY: рост = сильный доллар = сжатие (-1), падение = расширение (+1)
    if dxy_change is not None:
        if dxy_change > 3:
            score -= 1
            parts.append("рост DXY (сильный доллар)")
        elif dxy_change < -3:
            score += 1
            parts.append("падение DXY (слабый доллар)")

    # 10Y: высокие доходности = сжатие
    if treasury_10y is not None:
        if treasury_10y > 4.5:
            score -= 1
            parts.append("высокие доходности 10Y")
        elif treasury_10y < 3.0:
            score += 1
            parts.append("низкие доходности 10Y")

    signal = max(-1, min(1, score))
    if signal > 0:
        interp = "ликвидность расширяется"
    elif signal < 0:
        interp = "ликвидность сжимается"
    else:
        interp = "нейтральная среда"

    if parts:
        interp += f" ({'; '.join(parts)})"
    if sp_btc_corr is not None:
        interp += f". Корреляция BTC-S&P500: {sp_btc_corr:.2f}"

    return signal, interp


def get_macro_data(btc_prices: Optional[List[float]] = None) -> Optional[Dict]:
    """
    Получить макроэкономические данные.
    
    Args:
        btc_prices: список цен BTC за последние N дней (для корреляции с S&P).
                    Если None — корреляция не считается.
    
    Returns:
        {
            "fed_funds_rate": float | None,
            "treasury_10y": float | None,
            "dxy": float | None,
            "dxy_30d_change_pct": float | None,
            "sp500": float | None,
            "sp500_btc_correlation": float | None,
            "macro_signal": int,
            "interpretation": str
        } или None при критической ошибке
    """
    result: Dict[str, Any] = {
        "fed_funds_rate": None,
        "treasury_10y": None,
        "dxy": None,
        "dxy_30d_change_pct": None,
        "sp500": None,
        "sp500_btc_correlation": None,
        "macro_signal": 0,
        "interpretation": "нет данных (нужен FRED_API_KEY)",
    }

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.debug("FRED_API_KEY не задан в окружении — макро-данные недоступны")
        return result

    # Federal Funds Rate (месячные данные — берём последнее)
    fed = _get_latest_fred(SERIES_FEDFUNDS)
    result["fed_funds_rate"] = fed

    # 10Y Treasury
    treasury = _get_latest_fred(SERIES_DGS10)
    result["treasury_10y"] = treasury

    # DXY (Trade Weighted Dollar Index)
    dxy_obs = _get_fred_observations(SERIES_DTWEXBGS, limit=35)
    if dxy_obs:
        latest = _parse_fred_value(dxy_obs[0])
        oldest = _parse_fred_value(dxy_obs[-1]) if len(dxy_obs) > 1 else latest
        result["dxy"] = latest
        if latest and oldest and oldest > 0:
            result["dxy_30d_change_pct"] = (latest - oldest) / oldest * 100

    # S&P 500 и корреляция с BTC
    sp_obs = _get_fred_observations(SERIES_SP500, limit=35)
    if sp_obs and btc_prices and len(btc_prices) >= 20:
        sp_values = []
        for o in sp_obs:
            v = _parse_fred_value(o)
            if v is not None:
                sp_values.append(v)
        sp_values = list(reversed(sp_values))
        # Выравниваем длины
        n = min(len(sp_values), len(btc_prices), 30)
        if n >= 5:
            sp_slice = sp_values[-n:]
            btc_slice = btc_prices[-n:]
            sp_returns = [(sp_slice[i] - sp_slice[i - 1]) / sp_slice[i - 1] for i in range(1, n)]
            btc_returns = [(btc_slice[i] - btc_slice[i - 1]) / btc_slice[i - 1] for i in range(1, n)]
            result["sp500"] = sp_slice[-1]
            result["sp500_btc_correlation"] = _compute_correlation(btc_returns, sp_returns)
    elif sp_obs:
        result["sp500"] = _parse_fred_value(sp_obs[0])

    result["macro_signal"], result["interpretation"] = _interpret_macro(result)
    return result
