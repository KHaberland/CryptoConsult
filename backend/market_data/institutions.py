"""
Институциональный фактор: ETF притоки/оттоки, крупные покупки, регуляторные события.
Опционально: Coinglass API (ETF), CryptoPanic API (новости).
"""

import logging
import os
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

COINGLASS_BASE = "https://open-api-v4.coinglass.com"
# CryptoPanic API (бесплатный DEVELOPER): /api/developer/v2/posts/
# Ограничения: News Delay 24ч, 20 новостей, 2 запроса/сек, 100 запросов/мес, только Title+Description
CRYPTOPANIC_BASE = "https://cryptopanic.com/api/developer/v2"


def _get_btc_etf_coinglass() -> Optional[Dict]:
    """
    ETF данные через Coinglass: список ETF, AUM, притоки/оттоки.
    Требует COINGLASS_API_KEY.
    """
    api_key = os.environ.get("COINGLASS_API_KEY")
    if not api_key:
        return None
    try:
        # Список Bitcoin ETF
        r_list = requests.get(
            f"{COINGLASS_BASE}/api/etf/bitcoin/list",
            headers={"CG-API-KEY": api_key},
            timeout=15
        )
        if not r_list.ok:
            return None
        data_list = r_list.json()
        if data_list.get("code") != "0":
            return None
        etfs = data_list.get("data", [])

        # История потоков за 7 дней
        r_flow = requests.get(
            f"{COINGLASS_BASE}/api/etf/bitcoin/flow-history",
            headers={"CG-API-KEY": api_key},
            timeout=15
        )
        flow_data = []
        if r_flow.ok:
            data_flow = r_flow.json()
            if data_flow.get("code") == "0":
                flow_data = data_flow.get("data", [])[:7]

        total_aum = sum(float(e.get("aum_usd", 0) or 0) for e in etfs)
        total_btc = sum(
            float(e.get("asset_details", {}).get("btc_holding", 0) or 0)
            for e in etfs
        )
        flow_7d = sum(float(f.get("flow_usd", 0) or 0) for f in flow_data)
        flow_1d = float(flow_data[0].get("flow_usd", 0)) if flow_data else 0

        # Топ ETF по AUM
        top_etfs = sorted(
            [{"ticker": e.get("ticker"), "aum": float(e.get("aum_usd", 0) or 0),
              "btc_change_7d": float(e.get("asset_details", {}).get("btc_change_7d", 0) or 0)}
             for e in etfs],
            key=lambda x: x["aum"],
            reverse=True
        )[:5]

        return {
            "etf_count": len(etfs),
            "total_aum_usd": total_aum,
            "total_btc_holdings": total_btc,
            "flow_1d_usd": flow_1d,
            "flow_7d_usd": flow_7d,
            "top_etfs": top_etfs,
            "interpretation": _interpret_etf_flows(flow_1d, flow_7d),
        }
    except Exception as e:
        logger.warning(f"Ошибка Coinglass ETF: {e}")
        return None


def _interpret_etf_flows(flow_1d: float, flow_7d: float) -> str:
    """Интерпретация ETF потоков."""
    if flow_7d > 500_000_000:
        return "сильный приток в ETF (институциональный спрос)"
    if flow_7d < -500_000_000:
        return "отток из ETF (институциональная осторожность)"
    if flow_1d > 100_000_000:
        return "приток в ETF за день"
    if flow_1d < -100_000_000:
        return "отток из ETF за день"
    return "нейтральные потоки ETF"


def _fetch_cryptopanic_posts(api_key: str, filter_name: str) -> List[Dict]:
    """Один запрос к CryptoPanic API с заданным фильтром."""
    try:
        r = requests.get(
            f"{CRYPTOPANIC_BASE}/posts/",
            params={
                "auth_token": api_key,
                "filter": filter_name,
                "currencies": "BTC",
                "kind": "news",
                "public": "true",
            },
            timeout=10
        )
        if not r.ok:
            logger.warning(f"CryptoPanic API ({filter_name}): HTTP {r.status_code} — {r.text[:200]}")
            return []
        data = r.json()
        results = data.get("results") or data.get("data") or data.get("posts") or []
        if not isinstance(results, list):
            return []
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", {}).get("title", "") if isinstance(item.get("source"), dict) else "",
                "published_at": item.get("published_at", ""),
                "sentiment": item.get("sentiment"),
                "filter": filter_name,
            }
            for item in results
        ]
    except Exception as e:
        logger.warning(f"Ошибка CryptoPanic ({filter_name}): {e}")
        return []


def _get_crypto_news() -> Optional[List[Dict]]:
    """
    Крипто-новости через CryptoPanic API v1 (CRYPTOPANIC_API_KEY).
    Объединяет hot (тренды) и important (регуляторика, институции).
    """
    api_key = (os.environ.get("CRYPTOPANIC_API_KEY") or os.environ.get("CRYPTOPANIC_KEY") or "").strip()
    if not api_key:
        return None
    # hot — популярные; important — регуляторика, SEC, листинги
    hot = _fetch_cryptopanic_posts(api_key, "hot")
    important = _fetch_cryptopanic_posts(api_key, "important")
    # Объединяем, убираем дубли по title, important в приоритете
    seen = set()
    merged = []
    for item in important + hot:
        t = (item.get("title") or "").strip()
        if t and t not in seen:
            seen.add(t)
            merged.append(item)
    return merged[:10] if merged else None


def get_btc_institutions() -> Optional[Dict]:
    """
    Получить институциональные данные по Bitcoin.
    
    Returns:
        {
            "etf_count": int,
            "total_aum_usd": float,
            "total_btc_holdings": float,
            "flow_1d_usd": float,
            "flow_7d_usd": float,
            "top_etfs": list,
            "etf_interpretation": str,
            "news_headlines": list,
            "summary": str  # для LLM
        } или None
    """
    result: Dict[str, Any] = {
        "etf_count": 0,
        "total_aum_usd": 0,
        "total_btc_holdings": 0,
        "flow_1d_usd": 0,
        "flow_7d_usd": 0,
        "top_etfs": [],
        "etf_interpretation": "Анализ ETF недоступен, нужен платный API key.",
        "news_headlines": [],
        "summary": "",
    }

    etf_data = _get_btc_etf_coinglass()
    if etf_data:
        result.update(etf_data)
        result["etf_interpretation"] = etf_data.get("interpretation", result["etf_interpretation"])

    news = _get_crypto_news()
    if news:
        result["news_headlines"] = news

    # Сводка для LLM
    parts = []
    if result["total_aum_usd"] > 0:
        parts.append(f"ETF AUM: ${result['total_aum_usd']/1e9:.1f}B, BTC: {result['total_btc_holdings']:,.0f}")
    if result["flow_7d_usd"] != 0:
        parts.append(f"Поток 7д: ${result['flow_7d_usd']/1e6:+.0f}M")
    if result["etf_interpretation"] and "недоступен" not in result["etf_interpretation"]:
        parts.append(result["etf_interpretation"])
    if result["news_headlines"]:
        titles = [n["title"][:80] for n in result["news_headlines"][:5]]
        parts.append("Новости (CryptoPanic): " + "; ".join(titles))
    # Ограничения данных: всегда добавляем пояснение
    limitations = []
    if result["total_aum_usd"] == 0:
        limitations.append("Анализ ETF недоступен, нужен платный API key.")
    limitations.append(
        "Новости CryptoPanic доступны только за прошедшие сутки (недостоверны); "
        "для актуальных новостей нужен платный API key."
    )
    if parts:
        result["summary"] = ". ".join(parts) + " Ограничения: " + " ".join(limitations)
    else:
        result["summary"] = "Нет институциональных данных. " + " ".join(limitations)

    return result
