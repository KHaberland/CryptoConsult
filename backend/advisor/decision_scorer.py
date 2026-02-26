"""
Алгоритм принятия решения BUY / HOLD / REDUCE на основе 5 блоков анализа.
Этап 2, Шаг 1: Пять блоков с весами.
Этап 2, Шаг 2: Формула итогового балла.

| Блок | Название              | Вес | Критерии оценки                                    |
|------|-----------------------|-----|----------------------------------------------------|
| A    | Рыночная структура    | 25% | Цена выше MA200 → +1; Higher High → +1; иначе -1   |
| B    | Импульс               | 20% | RSI < 30 → +1; RSI > 70 → -1; MACD вверх/вниз ±1   |
| C    | Деривативы            | 20% | Funding + → -1; Funding − → +1; Ликвидации лонгов → +1; OI перегрев → -1 |
| D    | Он-чейн               | 20% | Отток с бирж → +1; Приток → -1; LTH +1; SOPR < 1 → +1 |
| E    | Макро и ликвидность   | 15% | Смягчение ФРС → +1; Рост DXY → -1; F&G страх/эйфория ±1 |

Шаг 2. Формула итогового балла:
    Итог = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) + (E × 0.15)
    Диапазон: от -2 до +2.

Шаг 3. Сигнал: >0.75 BUY, [-0.75..0.75] HOLD, <-0.75 REDUCE.
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass

# Шаг 2: Веса блоков для формулы итогового балла
WEIGHT_A = 0.25  # Рыночная структура
WEIGHT_B = 0.20  # Импульс
WEIGHT_C = 0.20  # Деривативы
WEIGHT_D = 0.20  # Он-чейн
WEIGHT_E = 0.15  # Макро и ликвидность

# Шаг 3: Пороги преобразования балла в сигнал
BUY_THRESHOLD = 0.75    # > +0.75 → BUY
REDUCE_THRESHOLD = -0.75  # < -0.75 → REDUCE


@dataclass
class ScorerInput:
    """Входные данные для расчёта скора."""
    price: float
    ma20: float
    ma50: float
    ma200: float
    rsi: float
    macd_line: float
    macd_prev: Optional[float]  # MACD 1 период назад (для направления)
    funding_rate: float
    open_interest_usd: float
    open_interest_prev: Optional[float]  # OI 7 дней назад для тренда
    fear_greed_value: int
    # Он-чейн: 0 = нейтрально, +1 = отток с бирж, -1 = приток
    exchange_flow_signal: int = 0
    lth_signal: int = 0
    sopr_signal: int = 0
    # Макро: -1 = сжатие, 0 = нейтрально, +1 = расширение
    macro_signal: int = 0
    # Higher High / Lower Low: +1 = HH, -1 = LL, 0 = нейтрально
    structure_signal: int = 0
    # Ликвидации лонгов 7д: +1 если капитуляция (лонгов > шортов, объём > порога)
    liquidations_long_signal: int = 0


class DecisionScorer:
    """
    Расчёт итогового балла и сигнала BUY / HOLD / REDUCE.
    
    Блоки:
    A — Рыночная структура (25%)
    B — Импульс (20%)
    C — Деривативы (20%)
    D — Он-чейн (20%)
    E — Макро и ликвидность (15%)
    """
    
    def _block_a_structure(self, inp: ScorerInput) -> int:
        """
        Блок A: Рыночная структура (25%). -2 до +2.
        Критерии: Цена выше MA200 → +1; Higher High → +1;
                  Ниже MA200 → -1; Lower Low → -1
        """
        score = 0
        if inp.ma200 and inp.ma200 > 0:
            if inp.price > inp.ma200:
                score += 1
            else:
                score -= 1
        if inp.structure_signal > 0:
            score += 1
        elif inp.structure_signal < 0:
            score -= 1
        return max(-2, min(2, score))
    
    def _block_b_momentum(self, inp: ScorerInput) -> int:
        """
        Блок B: Импульс (20%). -2 до +2.
        Критерии: RSI < 30 → +1; RSI > 70 → -1;
                  MACD вверх → +1; MACD вниз → -1
        """
        score = 0
        if inp.rsi < 30:
            score += 1
        elif inp.rsi > 70:
            score -= 1
        if inp.macd_prev is not None:
            if inp.macd_line > inp.macd_prev:
                score += 1
            elif inp.macd_line < inp.macd_prev:
                score -= 1
        else:
            if inp.macd_line > 0:
                score += 1
            elif inp.macd_line < 0:
                score -= 1
        return max(-2, min(2, score))
    
    def _block_c_derivatives(self, inp: ScorerInput) -> int:
        """
        Блок C: Деривативы (20%). -2 до +2.
        Критерии: Funding сильно + → -1; Funding − → +1;
                  Ликвидации лонгов → +1; Перегруженный OI → -1
        """
        score = 0
        # Funding сильно положительный (>0.0001) → -1, отрицательный → +1
        if inp.funding_rate > 0.0001:
            score -= 1
        elif inp.funding_rate < -0.00005:
            score += 1
        # Ликвидации лонгов (капитуляция) → +1
        if inp.liquidations_long_signal > 0:
            score += 1
        # Перегруженный OI → -1 (рост OI > 10% за неделю — перегрев)
        if inp.open_interest_prev and inp.open_interest_prev > 0:
            oi_change = (inp.open_interest_usd - inp.open_interest_prev) / inp.open_interest_prev
            if oi_change > 0.1:
                score -= 1
        return max(-2, min(2, score))
    
    def _block_d_onchain(self, inp: ScorerInput) -> int:
        """
        Блок D: Он-чейн (20%). -2 до +2.
        Критерии: Отток с бирж → +1; Приток на биржи → -1;
                  Рост LTH → +1; SOPR < 1 → +1
        """
        score = inp.exchange_flow_signal + inp.lth_signal + inp.sopr_signal
        return max(-2, min(2, score))
    
    def _block_e_macro(self, inp: ScorerInput) -> int:
        """
        Блок E: Макро и ликвидность (15%). -2 до +2.
        Критерии: Смягчение ФРС → +1; Рост DXY → -1;
                  Падение S&P → -1; Рост ликвидности → +1
        + Fear & Greed: крайний страх → +1, эйфория → -1
        """
        score = inp.macro_signal
        # Fear & Greed: крайний страх → +1, эйфория → -1
        if inp.fear_greed_value < 25:
            score += 1
        elif inp.fear_greed_value > 75:
            score -= 1
        return max(-2, min(2, score))
    
    def _compute_total_score(self, blocks: Dict[str, int]) -> float:
        """
        Шаг 2. Формула итогового балла.
        Итог = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) + (E × 0.15)
        Диапазон: от -2 до +2.
        """
        total = (
            blocks.get("A", 0) * WEIGHT_A
            + blocks.get("B", 0) * WEIGHT_B
            + blocks.get("C", 0) * WEIGHT_C
            + blocks.get("D", 0) * WEIGHT_D
            + blocks.get("E", 0) * WEIGHT_E
        )
        return max(-2.0, min(2.0, total))
    
    def _score_to_signal(self, total: float) -> str:
        """
        Шаг 3. Преобразование итогового балла в сигнал.
        | Итоговый балл      | Сигнал  |
        | > +0.75            | BUY     |
        | от -0.75 до +0.75  | HOLD    |
        | < -0.75            | REDUCE  |
        """
        if total > BUY_THRESHOLD:
            return "BUY"
        if total < REDUCE_THRESHOLD:
            return "REDUCE"
        return "HOLD"
    
    def compute(
        self,
        inp: ScorerInput
    ) -> Tuple[float, str, Dict[str, int]]:
        """
        Вычислить итоговый балл и сигнал.
        Итог = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) + (E × 0.15).
        Диапазон: -2 до +2. >0.75 BUY, [-0.75..0.75] HOLD, <-0.75 REDUCE.

        Returns:
            (итоговый_балл, сигнал, {"A": int, "B": int, "C": int, "D": int, "E": int})
        """
        a = self._block_a_structure(inp)
        b = self._block_b_momentum(inp)
        c = self._block_c_derivatives(inp)
        d = self._block_d_onchain(inp)
        e = self._block_e_macro(inp)
        
        blocks = {"A": a, "B": b, "C": c, "D": d, "E": e}
        # Шаг 2: Итог = (A × 0.25) + (B × 0.20) + (C × 0.20) + (D × 0.20) + (E × 0.15)
        total = self._compute_total_score(blocks)
        # Шаг 3: Преобразование в сигнал
        signal = self._score_to_signal(total)
        return total, signal, blocks
