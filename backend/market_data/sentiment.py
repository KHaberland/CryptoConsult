"""
Блок 8 — Сентимент: Fear & Greed, медийный фон, интерпретация.
Источники: Alternative.me (F&G), CryptoPanic (новости через institutions).
"""

import logging
from typing import Optional, Dict, Any, List

from .fear_greed import get_fear_greed_index

logger = logging.getLogger(__name__)

# Маппинг F&G classification → русская интерпретация
FNG_RU = {
    "Extreme Fear": "крайний страх",
    "Fear": "страх",
    "Neutral": "нейтрально",
    "Greed": "жадность",
    "Extreme Greed": "эйфория",
}


def _interpret_fng(value: int) -> str:
    """Краткая интерпретация для LLM: страх / апатия / жадность / эйфория."""
    if value < 25:
        return "крайний страх — возможная зона накопления"
    if value < 45:
        return "страх / осторожность"
    if value < 55:
        return "нейтрально / апатия"
    if value < 75:
        return "жадность — осторожность с FOMO"
    return "эйфория — высокий риск коррекции"


def _aggregate_news_sentiment(news: List[Dict]) -> Dict[str, Any]:
    """Агрегация тональности новостей из CryptoPanic."""
    pos = neg = neu = 0
    for item in news:
        s = (item.get("sentiment") or "").lower()
        if s in ("positive", "bullish"):
            pos += 1
        elif s in ("negative", "bearish"):
            neg += 1
        else:
            neu += 1
    total = pos + neg + neu
    if total == 0:
        return {"positive": 0, "negative": 0, "neutral": 0, "interpretation": "нет данных"}
    if pos > neg and pos > neu:
        interp = "позитивный медийный фон"
    elif neg > pos and neg > neu:
        interp = "негативный медийный фон"
    else:
        interp = "смешанный / нейтральный медийный фон"
    return {
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "interpretation": interp,
    }


def get_btc_sentiment(institutions: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Получить блок сентимента для раздела 8.
    
    Args:
        institutions: результат get_btc_institutions() — для news_headlines и sentiment.
    
    Returns:
        {
            "fear_greed_value": int,
            "fear_greed_classification": str,
            "fear_greed_interpretation": str,
            "news_sentiment": {"positive": int, "negative": int, "neutral": int, "interpretation": str},
            "summary": str  # для LLM
        }
    """
    fng = get_fear_greed_index()
    value = fng.get("value", 50) if fng else 50
    classification = fng.get("classification", "Neutral") if fng else "Neutral"
    classification_ru = FNG_RU.get(classification, classification)
    interpretation = _interpret_fng(value)

    news_sentiment = {"positive": 0, "negative": 0, "neutral": 0, "interpretation": "нет данных"}
    if institutions and institutions.get("news_headlines"):
        news_sentiment = _aggregate_news_sentiment(institutions["news_headlines"])

    parts = [f"Fear & Greed: {value} ({classification_ru}) — {interpretation}"]
    if news_sentiment["interpretation"] != "нет данных":
        parts.append(
            f"Медийный фон: {news_sentiment['interpretation']} "
            f"(+{news_sentiment['positive']}/-{news_sentiment['negative']}/{news_sentiment['neutral']})"
        )
    summary = ". ".join(parts)

    return {
        "fear_greed_value": value,
        "fear_greed_classification": classification_ru,
        "fear_greed_interpretation": interpretation,
        "news_sentiment": news_sentiment,
        "summary": summary,
    }
