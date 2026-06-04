"""
Сервис ИИ-консультанта.
"""

import json
import logging
import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple

import requests
from django.conf import settings
from django.core.cache import cache as django_cache
from django.db import transaction
from openai import OpenAI

from portfolios.models import Portfolio, FiatCashFlow
from portfolios.services import PriceService
from users.models import InvestorProfile
from .models import ChatMessage

logger = logging.getLogger(__name__)


def _fmt_inst_news(inst_dict: dict) -> str:
    """Форматирование новостей CryptoPanic для контекста LLM."""
    headlines = inst_dict.get("news_headlines") or []
    if not headlines:
        return "нет данных"
    return "; ".join((h.get("title") or "")[:80] for h in headlines[:5])


_FX_CACHE_KEY_USD_EUR = 'fx_rate_usd_eur'
_FX_CACHE_TTL_SECONDS = 60 * 60  # 1 час


def _fx_rate(from_cur: str, to_cur: str) -> Tuple[Decimal, bool]:
    """
    Курс конвертации `from_cur → to_cur` для подсистемы FiatCashFlow (PLAN11).

    Поддерживаются только 'USD' и 'EUR'. Никакой истории курсов не хранит —
    это снимок «сейчас», результат кэшируется в Django-cache на 1 час.

    Args:
        from_cur: исходная валюта ('USD' | 'EUR').
        to_cur: целевая валюта ('USD' | 'EUR').

    Returns:
        Кортеж ``(rate, stale)``:
        * ``rate`` — :class:`Decimal`, курс умножения суммы в ``from_cur``
          на получение суммы в ``to_cur``.
        * ``stale=True`` — внешний источник недоступен и rate возвращён как
          ``Decimal('1')`` (либо валюта неподдерживаемая). Вызывающий код
          должен пометить такие данные как «курс временно недоступен».
    """
    f = (from_cur or '').upper()
    t = (to_cur or '').upper()

    if f not in ('USD', 'EUR') or t not in ('USD', 'EUR'):
        logger.warning(
            "_fx_rate: неподдерживаемая пара %s→%s, возвращаю (1, stale=True)",
            from_cur, to_cur,
        )
        return Decimal('1'), True

    if f == t:
        return Decimal('1'), False

    usd_eur = django_cache.get(_FX_CACHE_KEY_USD_EUR)
    if usd_eur is None:
        try:
            response = requests.get(
                'https://api.exchangerate.host/latest',
                params={'base': 'USD', 'symbols': 'EUR'},
                timeout=5,
            )
            response.raise_for_status()
            payload = response.json() or {}
            rate_value = (payload.get('rates') or {}).get('EUR')
            if rate_value is None:
                raise ValueError(
                    f"exchangerate.host не вернул курс EUR: {payload!r}"
                )
            usd_eur = Decimal(str(rate_value))
            if usd_eur <= 0:
                raise ValueError(f"некорректный курс USD→EUR: {usd_eur}")
            django_cache.set(_FX_CACHE_KEY_USD_EUR, usd_eur, _FX_CACHE_TTL_SECONDS)
            logger.info("_fx_rate: получен USD→EUR=%s", usd_eur)
        except Exception as e:  # noqa: BLE001 — сторонний HTTP/JSON
            logger.warning("_fx_rate: USD→EUR недоступен (%s), отдаю 1.0 stale", e)
            return Decimal('1'), True
    elif not isinstance(usd_eur, Decimal):
        try:
            usd_eur = Decimal(str(usd_eur))
        except Exception:
            return Decimal('1'), True

    if usd_eur <= 0:
        return Decimal('1'), True

    if f == 'USD' and t == 'EUR':
        return usd_eur, False
    return (Decimal('1') / usd_eur), False


def _portfolio_fx_rate(
    portfolio: Portfolio,
    from_cur: str,
    to_cur: str,
) -> Tuple[Decimal, bool]:
    """Курс USD/EUR с приоритетом ручной настройки портфеля."""
    f = (from_cur or '').upper()
    t = (to_cur or '').upper()

    if f == t:
        return Decimal('1'), False

    manual_usd_eur = getattr(portfolio, 'manual_usd_eur_rate', None)
    if manual_usd_eur is not None:
        rate = Decimal(str(manual_usd_eur))
        if rate > 0:
            if f == Portfolio.CURRENCY_USD and t == Portfolio.CURRENCY_EUR:
                return rate, False
            if f == Portfolio.CURRENCY_EUR and t == Portfolio.CURRENCY_USD:
                return Decimal('1') / rate, False

    return _fx_rate(f, t)


class PortfolioAnalyzer:
    """Анализатор портфеля для расчёта метрик."""
    
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.price_service = PriceService()
    
    def _get_profile(self):
        """Получить профиль инвестора по session_id портфеля."""
        try:
            return InvestorProfile.objects.get(session_id=self.portfolio.session_id)
        except InvestorProfile.DoesNotExist:
            return None
    
    def _get_total_invested(self) -> float:
        """Сумма всех вложений: начальный взнос + дополнительные взносы."""
        contributions_sum = sum(
            float(c.amount) for c in self.portfolio.contributions.all()
        )
        return float(self.portfolio.initial_amount) + contributions_sum
    
    def _get_dca_corrected_invested(self) -> tuple:
        """
        Для DCA: вернуть (total_invested, units_scale).
        units_scale = множитель для units (1.0 = без коррекции).
        Если портфель создан с полной суммой вместо первой части — корректируем.
        """
        profile = self._get_profile()
        if not profile or not getattr(profile, 'use_dca', False):
            return self._get_total_invested(), 1.0
        
        dca_parts = profile.dca_parts or 4
        if profile.experience_level == 'beginner':
            dca_parts = 3
        if dca_parts <= 1:
            return self._get_total_invested(), 1.0
        
        investment_amount = float(profile.investment_amount or 0)
        if investment_amount <= 0:
            return self._get_total_invested(), 1.0
        
        first_part = investment_amount / dca_parts
        contributions_sum = sum(
            float(c.amount) for c in self.portfolio.contributions.all()
        )
        correct_total_invested = first_part + contributions_sum
        
        initial_amount = float(self.portfolio.initial_amount or 0)
        # Портфель создан с полной суммой? (initial_amount ≈ investment_amount)
        is_full_amount = (
            initial_amount > 0 and investment_amount > 0
            and abs(initial_amount - investment_amount) / investment_amount < 0.02
        )
        if is_full_amount:
            # Масштаб: (первая часть + взносы) / (полная сумма + взносы)
            wrong_total = initial_amount + contributions_sum
            correct_total = first_part + contributions_sum
            scale = correct_total / wrong_total if wrong_total > 0 else 1.0
            return correct_total_invested, scale
        
        return correct_total_invested, 1.0

    def get_units_scale(self) -> float:
        """Множитель для units (1.0 = без DCA-коррекции). Нужен для вывода средств."""
        _, scale = self._get_dca_corrected_invested()
        return scale

    def finalize_dca_scale(self) -> float:
        """
        «Затвердить» активную DCA-коррекцию: пересчитать units каждого актива
        и `Portfolio.initial_amount` так, чтобы дальнейшие операции работали
        в системе координат с `units_scale == 1.0`.

        Текущая отображаемая стоимость портфеля при этом не меняется
        (units * price = (units * scale) * price).

        Returns:
            Применённый scale. Если коррекция не была активна, возвращает 1.0
            и ничего не меняет.
        """
        scale = self.get_units_scale()
        if scale >= 1.0 - 1e-9:
            return 1.0

        with transaction.atomic():
            for asset in self.portfolio.assets.all():
                units = float(asset.units or 0)
                if units > 0:
                    asset.units = round(units * scale, 8)
                    asset.save(update_fields=['units'])

            new_initial = float(self.portfolio.initial_amount or 0) * scale
            self.portfolio.initial_amount = round(new_initial, 2)
            self.portfolio.save(update_fields=['initial_amount'])

        return scale

    def get_current_value(self) -> Dict:
        """Рассчитать текущую стоимость портфеля с учётом всех взносов."""
        assets = self.portfolio.assets.all()
        symbols = [asset.symbol for asset in assets]
        
        price_data = self.price_service.get_prices_with_changes(symbols)
        total_invested, units_scale = self._get_dca_corrected_invested()
        
        total_value = 0
        assets_info = []
        
        for asset in assets:
            symbol_data = price_data.get(asset.symbol, {})
            current_price = symbol_data.get('price', 0)
            change_24h = symbol_data.get('change_24h', 0)
            
            # Используем units если есть (учёт нескольких взносов)
            units = float(asset.units or 0)
            if units <= 0:
                # Fallback для старых портфелей
                asset_initial_value = total_invested * float(asset.percentage) / 100
                if asset.initial_price and current_price:
                    units = asset_initial_value / float(asset.initial_price)
                else:
                    units = 0
            
            # Коррекция DCA: портфель создан с полной суммой, показываем только внесённое
            units = units * units_scale
            asset_current_value = units * current_price if current_price else 0
            asset_initial_value = total_invested * float(asset.percentage) / 100
            
            total_value += asset_current_value
            
            profit_loss = asset_current_value - asset_initial_value
            profit_loss_percent = (
                (profit_loss / asset_initial_value * 100)
                if asset_initial_value > 0 else 0
            )
            
            assets_info.append({
                'symbol': asset.symbol,
                'name': asset.name,
                'percentage': float(asset.percentage),
                'units': units,
                'initial_value': asset_initial_value,
                'current_value': asset_current_value,
                'current_price': current_price,
                'change_24h': change_24h,
                'profit_loss': profit_loss,
                'profit_loss_percent': profit_loss_percent,
                'is_recommended': bool(getattr(asset, 'is_recommended', True)),
            })
        
        profit_loss = total_value - total_invested
        profit_loss_percent = (profit_loss / total_invested * 100) if total_invested > 0 else 0
        
        return {
            'initial_value': total_invested,
            'current_value': total_value,
            'profit_loss': profit_loss,
            'profit_loss_percent': profit_loss_percent,
            'assets': assets_info,
        }

    def get_fiat_pnl(self, currency: Optional[str] = None) -> Dict:
        """
        Прибыль/убыток портфеля по фиатному учёту :class:`FiatCashFlow` (PLAN11).

        В отличие от :meth:`get_current_value`, считает P&L не от
        ``Portfolio.initial_amount + Σ contributions``, а от суммы реально
        введённых на биржи/кошельки наличных (только депозиты, без вычета
        выводов в знаменателе процента).

        Args:
            currency: 'USD' или 'EUR'. ``None`` → ``portfolio.base_currency``.

        Returns:
            Словарь со следующими ключами:

            * ``currency`` (str): выбранная валюта вывода.
            * ``cash_in_total`` (float): Σ депозитов в ``currency``.
            * ``cash_out_total`` (float): Σ выводов в ``currency``.
            * ``net_cash_in`` (float): ``cash_in_total − cash_out_total``.
            * ``current_value`` (float): стоимость крипты в ``currency``
              (units × units_scale × цена CoinGecko в ``currency``).
            * ``profit_loss`` (float): ``current_value − net_cash_in``.
            * ``profit_loss_percent`` (float): ``profit_loss / cash_in_total
              × 100``. При ``cash_in_total == 0`` → ``0.0``.
            * ``no_cash_in`` (bool): ``True``, если ``cash_in_total == 0``
              (UI показывает CTA вместо нулей).
            * ``fx_stale`` (bool): ``True``, если хотя бы один FX-курс
              (``base → currency`` или EUR-цены через USD×FX) пришёл из
              fallback-источника.
        """
        base = (self.portfolio.base_currency or Portfolio.CURRENCY_USD).upper()
        cur = (currency or base).upper()
        if cur not in ('USD', 'EUR'):
            raise ValueError(
                f"Неподдерживаемая валюта: {currency!r}. Допустимо: 'USD', 'EUR'."
            )

        fx_stale = False
        if cur == base:
            fx_b2c = Decimal('1')
        else:
            fx_b2c, stale_b2c = _portfolio_fx_rate(self.portfolio, base, cur)
            if stale_b2c:
                fx_stale = True

        cash_in_base = Decimal('0')
        cash_out_base = Decimal('0')
        for flow in self.portfolio.fiat_cash_flows.all():
            amount_in_base = flow.amount_in_base
            if flow.kind == FiatCashFlow.KIND_DEPOSIT:
                cash_in_base += amount_in_base
            elif flow.kind == FiatCashFlow.KIND_WITHDRAWAL:
                cash_out_base += amount_in_base

        cash_in_total = float(cash_in_base * fx_b2c)
        cash_out_total = float(cash_out_base * fx_b2c)
        net_cash_in = cash_in_total - cash_out_total

        assets = list(self.portfolio.assets.all())
        symbols = [a.symbol for a in assets]
        manual_usd_eur = getattr(self.portfolio, 'manual_usd_eur_rate', None)
        if symbols and cur == 'EUR' and manual_usd_eur:
            usd_prices = self.price_service.get_prices_in_currency(symbols, 'USD')
            rate = float(Decimal(str(manual_usd_eur)))
            prices: Dict[str, float] = {
                symbol: float(price or 0) * rate
                for symbol, price in usd_prices.items()
            }
        else:
            prices = (
                self.price_service.get_prices_in_currency(symbols, cur)
                if symbols else {}
            )
        _, units_scale = self._get_dca_corrected_invested()

        current_value = 0.0
        for asset in assets:
            price = float(prices.get(asset.symbol, 0) or 0)
            units = float(asset.units or 0) * units_scale
            current_value += units * price

        # EUR-цены могли быть посчитаны как USD × FX (см. A3 fallback) —
        # помечаем такой ответ как fx_stale, чтобы фронт показал
        # «курс временно недоступен».
        if cur == 'EUR' and symbols and not fx_stale:
            try:
                known_sorted = sorted({
                    s.upper() for s in symbols
                    if s and s.upper() in self.price_service.SYMBOL_TO_ID
                })
                if known_sorted:
                    fallback_key = (
                        f"prices_eur:{','.join(known_sorted)}:eur_via_fx_fallback"
                    )
                    if self.price_service.cache.get_stale(fallback_key):
                        fx_stale = True
            except Exception:  # noqa: BLE001 — диагностический флаг, не критичный
                pass

        no_cash_in = cash_in_total <= 0
        profit_loss = current_value - net_cash_in
        profit_loss_percent = (
            (profit_loss / cash_in_total * 100) if cash_in_total > 0 else 0.0
        )

        return {
            'currency': cur,
            'cash_in_total': cash_in_total,
            'cash_out_total': cash_out_total,
            'net_cash_in': net_cash_in,
            'current_value': current_value,
            'profit_loss': profit_loss,
            'profit_loss_percent': profit_loss_percent,
            'no_cash_in': no_cash_in,
            'fx_stale': fx_stale,
        }

    def get_drawdown(self) -> Dict:
        """
        Рассчитать текущую просадку.
        Вывод средств НЕ считается просадкой. После вывода новая стоимость — база.
        Просадка = падение стоимости активов от базы (дата первого взноса / последнего вывода).
        """
        value_data = self.get_current_value()
        current_value = value_data['current_value']
        
        # База: стоимость после последнего вывода или начальная (если выводов не было)
        last_withdrawal = self.portfolio.withdrawals.first()
        if last_withdrawal and last_withdrawal.value_after is not None:
            base_value = float(last_withdrawal.value_after)
        else:
            base_value = value_data['initial_value']
        
        peak_value = max(base_value, current_value)
        
        if current_value >= peak_value or peak_value <= 0:
            drawdown = 0
        else:
            drawdown = (peak_value - current_value) / peak_value * 100
        
        return {
            'current_drawdown': drawdown,
            'peak_value': peak_value,
            'current_value': current_value,
            'base_value': base_value,
        }
    
    def get_time_metrics(self) -> Dict:
        """Получить временные метрики портфеля."""
        today = date.today()
        start_date = self.portfolio.start_date
        target_date = self.portfolio.target_date
        
        days_active = (today - start_date).days
        days_remaining = (target_date - today).days if target_date > today else 0
        total_days = (target_date - start_date).days
        progress_percent = (days_active / total_days * 100) if total_days > 0 else 0
        
        # Прошло ли 12 месяцев (для рекомендации о фиксации прибыли)
        months_active = days_active / 30
        can_consider_exit = months_active >= 12
        
        return {
            'start_date': start_date,
            'target_date': target_date,
            'days_active': days_active,
            'days_remaining': days_remaining,
            'progress_percent': min(progress_percent, 100),
            'months_active': months_active,
            'can_consider_exit': can_consider_exit,
        }


class AIAdvisorService:
    """Сервис для генерации рекомендаций через LLM."""
    
    # Быстрые команды
    QUICK_COMMANDS = {
        'status': 'Покажи текущий статус моего портфеля: стоимость, прибыль/убыток, состав активов.',
        'recommendation': 'Дай рекомендацию: что делать с портфелем сейчас?',
        'risk': 'Проанализируй риски моего портфеля.',
        'market': 'Какая сейчас ситуация на рынке криптовалют?',
        'drawdown': 'Какая сейчас просадка моего портфеля? Нужно ли что-то предпринять?',
        'rebalance': '__REBALANCE_COMMAND__',  # Специальная обработка
        'dca': 'Когда лучше сделать следующую покупку по DCA?',
        'exit': 'Стоит ли мне фиксировать прибыль сейчас?',
    }
    
    def __init__(self):
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "Введите свой API‑ключ в настройках. "
                "Создайте файл backend/.env и добавьте OPENROUTER_API_KEY=ваш_ключ (или OPENAI_API_KEY). "
                "См. шаблон в баннере на странице."
            )
        
        # Поддержка OpenRouter и других провайдеров через base_url
        base_url = getattr(settings, 'OPENAI_BASE_URL', None)
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
        self.price_service = PriceService()
    
    def get_system_prompt(self, session_id: str) -> str:
        """Генерирует системный промпт на основе профиля пользователя."""
        
        # Получаем профиль инвестора по session_id
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
        except InvestorProfile.DoesNotExist:
            profile = None
        
        # Получаем активный портфель по session_id
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        # Уровень детализации ответа в зависимости от опыта
        experience_styles = {
            'beginner': {
                'detail': 'кратко и просто, избегай технических терминов',
                'length': 'короткие ответы (2-3 абзаца)',
                'tone': 'дружелюбный и ободряющий'
            },
            'some': {
                'detail': 'с базовыми пояснениями',
                'length': 'средние ответы (3-4 абзаца)',
                'tone': 'информативный'
            },
            'medium': {
                'detail': 'подробно, можно использовать терминологию',
                'length': 'развёрнутые ответы',
                'tone': 'профессиональный'
            },
            'advanced': {
                'detail': 'детально с техническими терминами и аналитикой',
                'length': 'полные аналитические ответы',
                'tone': 'экспертный'
            }
        }
        
        # Базовый промпт
        prompt = """Ты — крипто-консультант для ДОЛГОСРОЧНЫХ инвесторов (холдеров).

⚡ ВАЖНО: У тебя ЕСТЬ ДОСТУП к актуальным ценам криптовалют!
Цены предоставляются тебе в реальном времени через CoinGecko API.
Они указаны в разделе "АКТУАЛЬНЫЕ РЫНОЧНЫЕ ДАННЫЕ" ниже.
НИКОГДА не говори пользователю, что у тебя нет доступа к ценам!
ВСЕГДА используй цены из предоставленных данных!

ТВОЯ РОЛЬ:
- Помогать инвесторам придерживаться долгосрочной стратегии (1-7 лет)
- Предоставлять информационную поддержку и образование
- Показывать АКТУАЛЬНЫЕ цены криптовалют (они есть в контексте!)
- Успокаивать при краткосрочной волатильности
- Предупреждать о рисках, когда это необходимо

ВАЖНЫЕ ПРАВИЛА:
1. НЕ давай финансовых советов — только информационная поддержка
2. НЕ рекомендуй активный трейдинг или краткосрочные спекуляции
3. ВСЕГДА предупреждай о рисках криптовалютных инвестиций
4. Отвечай на русском языке
5. Будь спокойным и рассудительным, не паникуй при волатильности
6. Рекомендуй удерживать позиции при краткосрочных просадках (если в пределах допустимого)
7. При больших просадках — предложи варианты, но не настаивай на продаже
8. ИСПОЛЬЗУЙ актуальные цены из раздела "АКТУАЛЬНЫЕ РЫНОЧНЫЕ ДАННЫЕ"!

СТАНДАРТНЫЕ DISCLAIMER:
- "Это не является финансовым советом"
- "Все инвестиции связаны с риском"
- "Прошлая доходность не гарантирует будущих результатов"
"""
        
        # Добавляем профиль инвестора
        if profile:
            style = experience_styles.get(
                profile.experience_level,
                experience_styles['beginner']
            )
            
            prompt += f"""
═══════════════════════════════════════
ПРОФИЛЬ ИНВЕСТОРА:
═══════════════════════════════════════
• Горизонт инвестирования: {profile.investment_horizon} лет
• Сумма инвестиций: ${profile.investment_amount:,.2f}
• Допустимая просадка: {profile.max_drawdown}%
• Уровень опыта: {profile.get_experience_level_display()}
• Использует DCA: {'Да' if profile.use_dca else 'Нет'}
• Нужна ликвидность: {'Да' if profile.needs_liquidity else 'Нет'}

СТИЛЬ ОТВЕТА:
• Детализация: {style['detail']}
• Длина: {style['length']}
• Тон: {style['tone']}

⚠️ ПРАВИЛА ПРОСАДКИ:
• Допустимая просадка пользователя: {profile.max_drawdown}%
• Если текущая просадка < {profile.max_drawdown}%: успокой, рекомендуй держать
• Если текущая просадка >= {profile.max_drawdown}%: предупреди, предложи варианты:
  1. Продолжить удержание (если веришь в долгосрок)
  2. Частично (10-20%) перевести в стейблкоины
  3. НЕ продавать всё в панике
"""
        
        # Добавляем информацию о портфеле
        if portfolio:
            analyzer = PortfolioAnalyzer(portfolio)
            value_data = analyzer.get_current_value()
            drawdown_data = analyzer.get_drawdown()
            time_data = analyzer.get_time_metrics()
            
            assets_info = []
            for asset in value_data['assets']:
                profit_emoji = "📈" if asset['profit_loss'] >= 0 else "📉"
                assets_info.append(
                    f"  • {asset['symbol']}: {asset['percentage']}% | "
                    f"${asset['current_value']:,.2f} | "
                    f"{profit_emoji} {asset['profit_loss_percent']:+.1f}%"
                )
            
            assets_str = "\n".join(assets_info) if assets_info else "  Портфель пуст"
            
            profit_emoji = "📈" if value_data['profit_loss'] >= 0 else "📉"
            
            contributions_note = ""
            contributions_count = portfolio.contributions.count()
            if contributions_count > 0:
                contributions_note = f"\n• Взносов внесено: {contributions_count} (портфель растёт по мере DCA)"
            
            is_imported = bool(getattr(portfolio, 'is_imported', False))
            portfolio_kind = (
                "Импортированный (пользователь ввёл уже существующие позиции)"
                if is_imported
                else "Создан с нуля по методике сервиса"
            )

            prompt += f"""
═══════════════════════════════════════
ТЕКУЩИЙ ПОРТФЕЛЬ (АКТУАЛЬНЫЕ ДАННЫЕ):
═══════════════════════════════════════
• Название: {portfolio.name}
• Тип портфеля: {portfolio_kind}
• Дата начала: {portfolio.start_date}
• Целевой горизонт: {portfolio.target_years} лет
• Целевая дата: {time_data['target_date']}
• Дней активен: {time_data['days_active']}
• Дней осталось: {time_data['days_remaining']}
• Прогресс: {time_data['progress_percent']:.1f}%

💰 ФИНАНСЫ (с учётом всех внесённых взносов):
• Всего вложено: ${value_data['initial_value']:,.2f}
• Текущая стоимость: ${value_data['current_value']:,.2f}
• Прибыль/убыток: {profit_emoji} ${value_data['profit_loss']:+,.2f} ({value_data['profit_loss_percent']:+.1f}%)
• Текущая просадка: {drawdown_data['current_drawdown']:.1f}%{contributions_note}

📊 СОСТАВ ПОРТФЕЛЯ:
{assets_str}
"""

            # Особые правила для импортированного портфеля
            if is_imported:
                all_non_rec_assets = [
                    a for a in value_data['assets']
                    if a.get('is_recommended') is False
                ]
                # USDC трактуем как стратегический кэш (ликвидный резерв),
                # а не как «альткойн вне ТОП-10».
                usdc_assets = [
                    a for a in all_non_rec_assets if a.get('symbol') == 'USDC'
                ]
                non_rec_assets = [
                    a for a in all_non_rec_assets if a.get('symbol') != 'USDC'
                ]
                non_rec_str = (
                    ", ".join(
                        f"{a['symbol']} ({a['percentage']}%)"
                        for a in non_rec_assets
                    )
                    if non_rec_assets
                    else "нет"
                )
                prompt += f"""
═══════════════════════════════════════
⚠️ ВАЖНО: ИМПОРТИРОВАННЫЙ ПОРТФЕЛЬ
═══════════════════════════════════════
Пользователь уже владеет указанными активами (купил их ранее на бирже
или холодном кошельке). Это НЕ свежесозданный портфель по методике сервиса.

ПРАВИЛА ДЛЯ ТАКОГО ПОРТФЕЛЯ:
1. НЕ предлагай полностью пересоздавать портфель «с нуля» —
   это повлечёт лишние комиссии и налоги.
2. НЕ предлагай DCA-стратегию для уже купленных позиций
   (DCA относится только к будущим докупкам).
3. Анализируй ТЕКУЩИЙ состав и давай рекомендации
   по ПОСТЕПЕННОЙ ребалансировке (а не одномоментной).
4. Особое внимание удели позициям ВНЕ ТОП-10 ликвидных монет
   (они помечены `is_recommended=False`), ЗА ИСКЛЮЧЕНИЕМ стейблкоина
   USDC — он трактуется как стратегический ликвидный резерв (см. ниже).

Активы вне ТОП-10 ликвидных в этом портфеле (без учёта USDC): {non_rec_str}.
"""
                if usdc_assets:
                    usdc_str = ", ".join(
                        f"{a['percentage']}%" for a in usdc_assets
                    )
                    prompt += f"""
───────────────────────────────────────
💵 USDC — СТРАТЕГИЧЕСКИЙ КЭШ
───────────────────────────────────────
В портфеле присутствует доля стейблкоина USDC ({usdc_str}).
USDC выполняет функцию ликвидного резерва и инструмента управления риском,
поэтому НЕ считай его «альткойном вне ТОП-10» и НЕ предлагай его обменивать
на BTC/ETH «на ту же сумму».

ПРАВИЛА ПО USDC:
1. Допустимая доля USDC в портфеле: 5–15%. Если доля попадает в этот
   диапазон — это нормальная практика управления рисками в условиях
   рыночной волатильности, специально комментировать это не нужно.
2. Если доля USDC меньше 5% — можно мягко упомянуть, что небольшой
   ликвидный резерв полезен для докупок на коррекциях.
3. Если доля USDC больше 15% — можно мягко обратить внимание, что
   избыточный кэш снижает потенциальную доходность портфеля, и при
   подходящих рыночных условиях часть USDC можно перевести в
   инвестиционные активы (BTC/ETH/другие монеты ТОП-10).
4. Назначение USDC в портфеле:
   • докупка активов на коррекциях рынка;
   • ребалансировка портфеля;
   • обеспечение ликвидности.
5. Конвертация USDC в инвестиционные активы должна происходить
   ПО СИГНАЛАМ РЫНКА и стратегии распределения капитала,
   а не как «обязательная замена альткойна».
"""
                if non_rec_assets:
                    prompt += (
                        "Для каждого актива из списка «вне ТОП-10 (без учёта USDC)» "
                        "при подходящем запросе пользователя рекомендуй обмен на "
                        "актив из ТОП-10 (BTC, ETH или другую крупную монету), "
                        "объясняй риск низкой ликвидности и непригодности "
                        "альткойнов для долгосрочного холда. НО не настаивай — "
                        "решение остаётся за пользователем.\n"
                    )

            # Проверяем, можно ли рекомендовать выход
            if time_data['can_consider_exit'] and value_data['profit_loss_percent'] > 20:
                prompt += f"""
📌 ВАЖНО: Портфель активен более 12 месяцев и показывает прибыль {value_data['profit_loss_percent']:.1f}%.
При запросе о фиксации прибыли можно обсудить варианты:
1. Продолжить стратегию до целевой даты
2. Зафиксировать часть прибыли (10-30%)
"""
        
        return prompt
    
    def get_market_context(self, portfolio: Optional[Portfolio] = None) -> str:
        """Получает текущий контекст рынка."""
        
        # Загружаем ВСЕ поддерживаемые криптовалюты
        # Это позволяет консультанту отвечать на вопросы о любой монете
        all_symbols = PriceService.get_supported_symbols()
        
        # Получаем цены с изменениями для всех монет
        price_data = self.price_service.get_prices_with_changes(all_symbols)
        
        # Отладочный вывод
        logger.debug("Загружены цены для %d монет: %s", len(price_data), list(price_data.keys()))
        
        if not price_data:
            return """
═══════════════════════════════════════
⚠️ ДАННЫЕ О ЦЕНАХ ВРЕМЕННО НЕДОСТУПНЫ
═══════════════════════════════════════
Сервис цен временно недоступен. Отвечай на основе общих знаний о рынке,
но предупреди пользователя, что актуальные цены сейчас недоступны.
"""
        
        context = """
═══════════════════════════════════════
📊 АКТУАЛЬНЫЕ РЫНОЧНЫЕ ДАННЫЕ
═══════════════════════════════════════
⚠️ ВАЖНО: Данные ниже получены в РЕАЛЬНОМ ВРЕМЕНИ через CoinGecko API.
ТЫ ОБЯЗАН использовать ЭТИ цены при ответе пользователю!
НЕ говори что у тебя нет доступа к ценам — они предоставлены ниже!

"""
        
        for symbol, data in price_data.items():
            price = data.get('price', 0)
            change = data.get('change_24h', 0)
            emoji = "🟢" if change >= 0 else "🔴"
            context += f"  {emoji} {symbol}: ${price:,.2f} (изменение за 24ч: {change:+.2f}%)\n"
        
        context += """
═══════════════════════════════════════
Используй эти данные в своих ответах!
"""
        
        return context
    
    def get_market_forecast(self, days: int = 180) -> Dict:
        """
        Прогноз крипторынка на указанное количество дней вперёд.
        Возвращает 3 сценария: позитивный, негативный, базовый с вероятностями.
        
        Args:
            days: горизонт прогноза (30, 90, 180 и т.д.)
        """
        market_context = self.get_market_context()
        
        portfolio_desc = (
            "BTC 50%, ETH 30%, USDT 10%, BNB 2%, XRP 2%, SOL 2%, DOGE 2%, ADA 2%"
        )
        period_text = f"{days} дней" if days < 60 else f"{days // 30} месяцев"
        prompt = f"""Ты — крипто-консультант. Проанализируй текущую ситуацию на крипторынке и дай прогноз на {period_text} вперёд.

{market_context}

Сформируй 3 сценария развития крипторынка на ближайшие {period_text}. Вероятности должны в сумме давать 100%.

Затем определи сценарий с НАИБОЛЬШЕЙ вероятностью и опиши, как будет вести себя базовый портфель ({portfolio_desc}) спустя этот период при этом сценарии.

Ответь СТРОГО в формате JSON (без markdown, без пояснений):
{{
  "positive": {{
    "description": "Краткое описание позитивного сценария (2-3 предложения): рост рынка, факторы, ожидаемая динамика",
    "probability": число от 0 до 100
  }},
  "negative": {{
    "description": "Краткое описание негативного сценария (2-3 предложения): падение, риски, возможные причины",
    "probability": число от 0 до 100
  }},
  "base": {{
    "description": "Краткое описание базового сценария (2-3 предложения): боковое движение, умеренная волатильность",
    "probability": число от 0 до 100
  }},
  "portfolio_outlook": {{
    "most_likely_scenario": "positive" или "negative" или "base",
    "description": "Как будет вести себя портфель спустя {period_text} при наиболее вероятном сценарии: ожидаемая динамика стоимости, поведение активов, риски и возможности (3-5 предложений)"
  }}
}}

Важно: probability для positive + negative + base = 100. most_likely_scenario должен соответствовать сценарию с максимальной вероятностью. Отвечай только валидным JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты — крипто-консультант. Отвечай только валидным JSON без markdown."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.5,
            )
            
            text = response.choices[0].message.content.strip()
            # Убираем markdown-обёртку если есть
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines[0].strip().startswith("```json") else "\n".join(lines[1:-1])
            data = json.loads(text)
            
            # Нормализуем вероятности
            total = (
                float(data.get("positive", {}).get("probability", 0)) +
                float(data.get("negative", {}).get("probability", 0)) +
                float(data.get("base", {}).get("probability", 0))
            )
            if total > 0:
                for key in ("positive", "negative", "base"):
                    if key in data and "probability" in data[key]:
                        data[key]["probability"] = round(
                            float(data[key]["probability"]) / total * 100, 1
                        )
            
            result = {
                "days": days,
                "positive": data.get("positive", {"description": "", "probability": 0}),
                "negative": data.get("negative", {"description": "", "probability": 0}),
                "base": data.get("base", {"description": "", "probability": 0}),
            }
            # Добавляем прогноз портфеля (Этап 2)
            po = data.get("portfolio_outlook", {})
            if po:
                result["portfolio_outlook"] = {
                    "most_likely_scenario": po.get("most_likely_scenario", "base"),
                    "description": po.get("description", ""),
                }
            else:
                # Определяем наиболее вероятный сценарий по данным
                scenarios = [
                    ("positive", result["positive"]["probability"]),
                    ("negative", result["negative"]["probability"]),
                    ("base", result["base"]["probability"]),
                ]
                most_likely = max(scenarios, key=lambda x: x[1])[0]
                result["portfolio_outlook"] = {
                    "most_likely_scenario": most_likely,
                    "description": (
                        "При наиболее вероятном сценарии портфель может показать "
                        "умеренную динамику. Рекомендуется придерживаться стратегии DCA "
                        "и не реагировать на краткосрочную волатильность."
                    ),
                }
            return result
        except Exception as e:
            logger.error(f"Ошибка get_market_forecast ({days} дней): {e}")
            return {
                "days": days,
                "positive": {
                    "description": "Рост рынка на фоне институционального спроса и халвинга BTC.",
                    "probability": 35.0,
                },
                "negative": {
                    "description": "Коррекция из-за макроэкономических факторов и фиксации прибыли.",
                    "probability": 30.0,
                },
                "base": {
                    "description": "Боковое движение в диапазоне с умеренной волатильностью.",
                    "probability": 35.0,
                },
                "portfolio_outlook": {
                    "most_likely_scenario": "base",
                    "description": (
                        "При базовом сценарии (боковое движение) портфель BTC/ETH/альтов "
                        "может сохранить стоимость с умеренной волатильностью. "
                        "Стейблкоины обеспечат стабильность. Рекомендуется продолжать DCA."
                    ),
                },
            }
    
    def _compute_ema(self, prices: List[float], period: int) -> float:
        """Экспоненциальная скользящая средняя."""
        if not prices or period <= 0:
            return 0.0
        k = 2.0 / (period + 1)
        ema = sum(prices[:period]) / min(period, len(prices))
        for i in range(period, len(prices)):
            ema = prices[i] * k + ema * (1 - k)
        return ema
    
    def _compute_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """RSI за последние period периодов."""
        if len(prices) < period + 1:
            return None
        gains, losses = [], []
        for i in range(1, period + 1):
            change = prices[-i] - prices[-i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _compute_atr(self, prices: List[float], period: int = 14) -> Optional[float]:
        """ATR (Average True Range) — волатильность. Используем High-Low≈|close-close_prev|."""
        if len(prices) < period + 1:
            return None
        tr_list = []
        for i in range(1, len(prices)):
            tr = abs(prices[i] - prices[i - 1])
            tr_list.append(tr)
        if len(tr_list) < period:
            return None
        atr = sum(tr_list[-period:]) / period
        return atr
    
    def _compute_bollinger(self, prices: List[float], period: int = 20, k: float = 2.0) -> Optional[tuple]:
        """Bollinger Bands: (middle, upper, lower, bandwidth_pct)."""
        if len(prices) < period:
            return None
        slice_p = prices[-period:]
        middle = sum(slice_p) / period
        variance = sum((p - middle) ** 2 for p in slice_p) / period
        std = math.sqrt(variance) if variance > 0 else 0
        upper = middle + k * std
        lower = middle - k * std
        bandwidth = ((upper - lower) / middle * 100) if middle else 0
        return (middle, upper, lower, bandwidth)
    
    def get_btc_analysis(self, session_id: Optional[str] = None) -> Dict:
        """
        Глубокий анализ Bitcoin по 10-раздельному шаблону Crypto Market Report.
        Возвращает структурированный отчёт, сценарный прогноз, рекомендации и сигнал BUY/HOLD/REDUCE.
        session_id: для персонализации рекомендаций по профилю инвестора.
        """
        # Данные за 200 дней для MA200
        data = self.price_service.get_historical_prices_with_volumes("BTC", 200)
        if not data:
            data = self.price_service.get_historical_prices_with_volumes("BTC", 30)
        if not data:
            return {
                "error": "Не удалось загрузить данные BTC. Попробуйте позже.",
                "sections": [],
                "scenario_forecast": None,
                "profile_recommendations": None,
                "forecast_6months": "",
                "buy_recommendation": "",
                "signal": "HOLD",
                "signal_score": 0.0,
                "signal_blocks": {},
            }
        
        prices = [d["price"] for d in data]
        volumes = [d["volume"] for d in data]
        current_price = prices[-1] if prices else 0
        price_30d_ago = prices[-30] if len(prices) >= 30 else prices[0] if prices else 0
        price_change_30d = (
            ((current_price - price_30d_ago) / price_30d_ago * 100)
            if price_30d_ago else 0
        )
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        recent_volume = sum(volumes[-7:]) / 7 if len(volumes) >= 7 else (volumes[-1] if volumes else 0)
        
        ma20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else sum(prices) / len(prices)
        ma50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else sum(prices) / len(prices)
        ma200 = sum(prices[-200:]) / 200 if len(prices) >= 200 else (sum(prices) / len(prices) if prices else 0)
        ma_cross = "бычье" if ma20 > ma50 else "медвежье"
        ma_cross_50_200 = "золотой крест" if ma50 > ma200 else "мёртвый крест"
        
        rsi = self._compute_rsi(prices)
        rsi_val = rsi if rsi is not None else 50.0
        rsi_zone = "перекупленности" if rsi_val > 70 else "перепроданности" if rsi_val < 30 else "нейтральной"
        
        atr = self._compute_atr(prices)
        atr_val = atr if atr is not None else 0.0
        bb = self._compute_bollinger(prices)
        bb_str = ""
        if bb:
            bb_str = f"Bollinger: середина ${bb[0]:,.0f}, верх ${bb[1]:,.0f}, низ ${bb[2]:,.0f}, ширина полос {bb[3]:.1f}%"
        
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1] * 100)
        volatility = math.sqrt(sum(r**2 for r in returns) / len(returns)) if returns else 0
        
        ema12 = self._compute_ema(prices, 12)
        ema26 = self._compute_ema(prices, 26)
        macd_line = ema12 - ema26
        macd_signal = "бычий" if macd_line > 0 else "медвежий"
        # MACD предыдущий период (для направления)
        prices_prev = prices[:-1] if len(prices) > 1 else prices
        ema12_prev = self._compute_ema(prices_prev, 12) if len(prices_prev) >= 12 else ema12
        ema26_prev = self._compute_ema(prices_prev, 26) if len(prices_prev) >= 26 else ema26
        macd_prev = ema12_prev - ema26_prev if (prices_prev and len(prices_prev) >= 26) else None
        
        # Профиль инвестора (для раздела 10)
        profile = None
        if session_id:
            try:
                profile = InvestorProfile.objects.get(session_id=session_id)
            except InvestorProfile.DoesNotExist:
                pass

        # Fear & Greed, деривативы, он-чейн, макро, институции, сентимент
        try:
            from market_data import get_btc_derivatives, get_btc_onchain, get_macro_data, get_btc_institutions, get_btc_sentiment
            deriv = get_btc_derivatives()
            onchain = get_btc_onchain()
            macro = get_macro_data(btc_prices=prices)
            institutions = get_btc_institutions()
            sentiment = get_btc_sentiment(institutions)
        except ImportError:
            deriv = None
            onchain = None
            macro = None
            institutions = None
            sentiment = None

        fng_val = (sentiment or {}).get("fear_greed_value", 50)
        fng_class = (sentiment or {}).get("fear_greed_classification", "Neutral")
        funding_rate = deriv.get("funding_rate", 0.0) if deriv else 0.0
        oi_usd = deriv.get("open_interest_usd", 0) if deriv else 0
        oi_prev = deriv.get("open_interest_7d_ago_usd") if deriv else None

        # Ликвидации лонгов: капитуляция → +1 для блока C
        liquidations_long_signal = 0
        liq = (deriv or {}).get("liquidations_7d")
        if liq:
            long_liq = liq.get("long_liquidations_usd", 0) or 0
            short_liq = liq.get("short_liquidations_usd", 0) or 0
            total = liq.get("total_usd", 0) or (long_liq + short_liq)
            if total > 50_000_000 and long_liq > short_liq * 1.2:
                liquidations_long_signal = 1

        oc = onchain or {}
        exchange_flow_signal = oc.get("exchange_flow_signal", 0)
        lth_signal = oc.get("lth_signal", 0)
        sopr_signal = oc.get("sopr_signal", 0)
        macro_signal = (macro or {}).get("macro_signal", 0)
        
        # Структура: Higher High если цена > ma50 и ma50 > ma200
        structure_signal = 0
        if ma200 and ma200 > 0 and current_price > ma50 and ma50 > ma200:
            structure_signal = 1
        elif ma200 and ma200 > 0 and current_price < ma50 and ma50 < ma200:
            structure_signal = -1
        
        # Переменные для f-строки (избегаем UnboundLocalError в условиях)
        mc = macro or {}
        inst = institutions or {}
        s = sentiment or {}
        news_instruction = (
            "Новости доступны (с ограничением 24ч) — перечисли заголовки из контекста выше. "
            if inst.get("news_headlines")
            else "Новости недоступны (нужен API key). "
        )

        # DecisionScorer
        try:
            from .decision_scorer import DecisionScorer, ScorerInput
            scorer = DecisionScorer()
            inp = ScorerInput(
                price=current_price,
                ma20=ma20,
                ma50=ma50,
                ma200=ma200,
                rsi=rsi_val,
                macd_line=macd_line,
                macd_prev=macd_prev,
                funding_rate=funding_rate,
                open_interest_usd=oi_usd,
                open_interest_prev=oi_prev,
                fear_greed_value=fng_val,
                exchange_flow_signal=exchange_flow_signal,
                lth_signal=lth_signal,
                sopr_signal=sopr_signal,
                macro_signal=macro_signal,
                structure_signal=structure_signal,
                liquidations_long_signal=liquidations_long_signal,
            )
            signal_score, signal, signal_blocks = scorer.compute(inp)
        except Exception as e:
            logger.warning(f"DecisionScorer: {e}")
            signal_score, signal, signal_blocks = 0.0, "HOLD", {}
        
        data_context = f"""
═══════════════════════════════════════
📊 ДАННЫЕ BITCOIN (дневной + недельный таймфрейм)
═══════════════════════════════════════
• Текущая цена: ${current_price:,.2f}
• Цена 30 дней назад: ${price_30d_ago:,.2f}
• Изменение за 30 дней: {price_change_30d:+.2f}%
• Средний объём: ${avg_volume:,.0f}
• Объём последние 7 дней: ${recent_volume:,.0f}
• MA(20): ${ma20:,.2f}
• MA(50): ${ma50:,.2f}
• MA(200): ${ma200:,.2f}
• Пересечение MA20/MA50: {ma_cross}
• MA50/MA200: {ma_cross_50_200}
• RSI(14): {rsi_val:.1f} (зона {rsi_zone})
• MACD: {macd_signal} (линия: {macd_line:+.2f})
• ATR(14): ${atr_val:,.0f}
• {bb_str}
• Волатильность (дневная): {volatility:.2f}%
• Funding Rate (8h): {funding_rate:.4%}
• Open Interest (USD): ${oi_usd:,.0f}
• Open Interest 7д назад: ${(deriv or {}).get('open_interest_7d_ago_usd', oi_usd):,.0f}
• Изменение OI за 7д: {(deriv or {}).get('open_interest_7d_change_pct', 0):+.1f}%
• Long/Short ratio: {(deriv or {}).get('long_short_ratio', 1.0):.2f} (лонги {(deriv or {}).get('long_account_pct', 50):.1f}% / шорты {(deriv or {}).get('short_account_pct', 50):.1f}%)
• Ликвидации 7д: {f"${((deriv or {}).get('liquidations_7d') or {}).get('total_usd', 0):,.0f}" if (deriv or {}).get('liquidations_7d') else 'нет данных (нужен COINGLASS_API_KEY)'}
• Вывод по деривативам: {(deriv or {}).get('interpretation', 'нейтральный') or 'нет данных'}
• Active addresses (24h): {(onchain or {}).get('active_addresses', 0):,.0f}
• Active addresses 7д ср.: {(onchain or {}).get('active_addresses_7d_avg', 0):,.0f}
• Транзакций 24h: {(onchain or {}).get('transactions_24h', 0):,.0f}
• MVRV: {(onchain or {}).get('mvrv') or "нет данных (для MVRV и SOPR в вашем проекте нужен платный Glassnode API или реализация расчёта по открытым данным)"}
• SOPR: {(onchain or {}).get('sopr') or "нет данных (для MVRV и SOPR в вашем проекте нужен платный Glassnode API или реализация расчёта по открытым данным)"}
• Exchange inflow BTC: {(onchain or {}).get('exchange_inflow_btc') or 'нет данных'}
• Exchange outflow BTC: {(onchain or {}).get('exchange_outflow_btc') or 'нет данных'}
• LTH supply %: {(onchain or {}).get('lth_supply_pct') or 'нет данных'}
• Вывод по он-чейн: {(onchain or {}).get('interpretation', 'нет данных')}

6. МАКРОЭКОНОМИКА (Liquidity Environment) — используй эти данные в разделе 6:
• ФРС (Fed Funds Rate): {f"{mc.get('fed_funds_rate'):.2f}%" if mc.get('fed_funds_rate') is not None else 'нет данных'}
• 10Y Treasury: {f"{mc.get('treasury_10y'):.2f}%" if mc.get('treasury_10y') is not None else 'нет данных'}
• DXY (индекс доллара): {f"{mc.get('dxy'):.2f}" if mc.get('dxy') is not None else 'нет данных'}
• Изменение DXY 30д: {f"{mc.get('dxy_30d_change_pct'):+.1f}%" if mc.get('dxy_30d_change_pct') is not None else 'нет данных'}
• S&P 500: {f"{mc.get('sp500'):,.0f}" if mc.get('sp500') is not None else 'нет данных'}
• Корреляция BTC-S&P500: {f"{mc.get('sp500_btc_correlation'):.2f}" if mc.get('sp500_btc_correlation') is not None else 'нет данных'}
• Вывод по макро: {mc.get('interpretation', 'нет данных')}
• ETF: {inst.get('etf_count', 0)} фондов, AUM ${inst.get('total_aum_usd', 0) / 1e9:.1f}B
• ETF поток 1д: ${inst.get('flow_1d_usd', 0) / 1e6:+.0f}M, 7д: ${inst.get('flow_7d_usd', 0) / 1e6:+.0f}M
• Институциональный вывод (ETF): {inst.get('etf_interpretation', 'нет данных')}
• Новости (CryptoPanic): {_fmt_inst_news(inst)}
• Сводка институций: {inst.get('summary', 'нет данных')}

8. СЕНТИМЕНТ:
• Fear & Greed Index: {s.get('fear_greed_value', 50)} ({s.get('fear_greed_classification', 'нейтрально')})
• Интерпретация F&G: {s.get('fear_greed_interpretation', 'нет данных')}
• Медийный фон: {s.get('news_sentiment', {}).get('interpretation', 'нет данных')} (позитив/негатив/нейтр: +{s.get('news_sentiment', {}).get('positive', 0)}/-{s.get('news_sentiment', {}).get('negative', 0)}/{s.get('news_sentiment', {}).get('neutral', 0)})
• Сводка сентимента: {s.get('summary', 'нет данных')}
"""

        profile_ctx = ""
        if profile:
            profile_ctx = f"""
ПРОФИЛЬ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ (для персонализации раздела 10):
• Горизонт: {profile.investment_horizon} лет
• Сумма: ${profile.investment_amount:,.0f}
• Допустимая просадка: {profile.max_drawdown}%
• Уровень опыта: {profile.get_experience_level_display()}
• DCA: {'да' if profile.use_dca else 'нет'}
• Нужна ликвидность: {'да' if profile.needs_liquidity else 'нет'}
Определи тип профиля пользователя (консервативный/умеренный/агрессивный) по max_drawdown и experience_level.
"""
        
        prompt = f"""Ты — крипто-консультант. Проведи профессиональный анализ Bitcoin по шаблону Crypto Market Report.

{data_context}
{profile_ctx}

СТРУКТУРА ОТВЕТА (10 разделов). Ответь СТРОГО в формате JSON (без markdown):

{{
  "executive_summary": "5-7 строк: текущий тренд, стадия цикла, основной риск, драйвер роста, базовый сценарий на 6 мес",
  "sections": [
    {{"title": "2. Рыночная структура (Market Structure)", "content": "Higher High/Lower Low, уровни поддержки/сопротивления, вывод: бычья/нейтральная/медвежья"}},
    {{"title": "3. Технические индикаторы (Momentum & Trend)", "content": "MA50/MA200, RSI, MACD, ATR, Bollinger — интерпретация"}},
    {{"title": "4. Деривативы (Risk & Leverage)", "content": "Funding Rate, Open Interest — рынок перегружен лонгами/очищен/нейтральный"}},
    {{"title": "5. Он-чейн аналитика (Network Health)", "content": "Active addresses, exchange flow, MVRV, SOPR — накопление/распределение/капитуляция. Когда MVRV/SOPR отсутствуют — укажи в скобках: для MVRV и SOPR в вашем проекте нужен платный Glassnode API или реализация расчёта по открытым данным"}},
    {{"title": "6. Макроэкономика (Liquidity Environment)", "content": "ОБЯЗАТЕЛЬНО используй фактические данные из блока '6. МАКРОЭКОНОМИКА' выше (ФРС, 10Y Treasury, DXY, S&P 500, корреляция). Если данные есть — включи числа и вывод по макро. Если везде 'нет данных' — укажи отсутствие данных."}},
    {{"title": "7. Институциональный фактор", "content": "ETF притоки/оттоки (если есть), крупные покупки, регуляторные события. {news_instruction}Ограничения: анализ ETF недоступен без платного API key."}},
    {{"title": "8. Сентимент", "content": "Fear & Greed, соцсети, медийный фон — страх/апатия/эйфория"}},
    {{"title": "9. Сценарный прогноз", "content": "Краткое резюме трёх сценариев (см. scenario_forecast)"}},
    {{"title": "10. Инвестиционные рекомендации по профилю", "content": "Краткое резюме (см. profile_recommendations)"}}
  ],
  "profile_recommendations": {{
    "conservative": {{"allocation": "70% BTC, 20% ETH, 10% стейбл", "description": "Для консервативных инвесторов"}},
    "moderate": {{"allocation": "60% BTC, 25% ETH, 15% альты", "description": "Для умеренных инвесторов"}},
    "aggressive": {{"allocation": "50% BTC, 30% ETH, 20% альты", "description": "Для агрессивных инвесторов"}},
    "user_profile_type": "консервативный/умеренный/агрессивный — тип профиля текущего пользователя",
    "user_recommendation": "Персонализированная рекомендация для текущего пользователя (2-4 предложения)"
  }},
  "scenario_forecast": {{
    "base": {{"probability": 60, "description": "Описание базового сценария на 6 мес", "price_range": "Диапазон цен BTC (напр. $90k-$120k)"}},
    "bullish": {{"probability": 25, "description": "Условия реализации альтернативного бычьего сценария", "conditions": "Условия (например: смягчение ФРС, рост ETF)"}},
    "negative": {{"probability": 15, "description": "Описание негативного сценария", "triggers": "Триггеры падения (напр. ужесточение ФРС, регуляторные риски)"}}
  }},
  "forecast_6months": "Прогноз на 6 месяцев (3-5 предложений)",
  "buy_recommendation": "Стоит ли покупать BTC сейчас? Да/нет, обоснование (2-4 предложения)"
}}

Важно: отвечай только валидным JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты — крипто-консультант. Отвечай только валидным JSON без markdown."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3500,
                temperature=0.5,
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1]) if lines else text
            data_out = json.loads(text)
            
            sections = []
            exec_summary = data_out.get("executive_summary", "")
            if exec_summary:
                sections.append({"title": "1. Резюме (Executive Summary)", "content": str(exec_summary)})
            raw_sections = data_out.get("sections", [])
            if isinstance(raw_sections, list):
                for s in raw_sections:
                    if isinstance(s, dict) and s.get("title"):
                        sections.append({
                            "title": str(s.get("title", "")),
                            "content": str(s.get("content", "")),
                        })

            scenario_forecast = data_out.get("scenario_forecast")


            def _normalize_scenario(sc: dict) -> dict:
                if not isinstance(sc, dict):
                    return {}
                return {
                    "probability": sc.get("probability", 0),
                    "description": sc.get("description", ""),
                    "price_range": sc.get("price_range", ""),
                    "conditions": sc.get("conditions", ""),
                    "triggers": sc.get("triggers", ""),
                }

            if scenario_forecast and isinstance(scenario_forecast, dict):
                scenario_forecast = {
                    "base": _normalize_scenario(scenario_forecast.get("base", {})),
                    "bullish": _normalize_scenario(scenario_forecast.get("bullish", {})),
                    "negative": _normalize_scenario(scenario_forecast.get("negative", {})),
                }
            else:
                scenario_forecast = None

            def _normalize_profile_rec(pr: dict) -> dict:
                if not isinstance(pr, dict):
                    return {}
                return {
                    "allocation": pr.get("allocation", ""),
                    "description": pr.get("description", ""),
                }

            pr_raw = data_out.get("profile_recommendations")
            profile_recommendations = None
            if pr_raw and isinstance(pr_raw, dict):
                profile_recommendations = {
                    "conservative": _normalize_profile_rec(pr_raw.get("conservative", {})),
                    "moderate": _normalize_profile_rec(pr_raw.get("moderate", {})),
                    "aggressive": _normalize_profile_rec(pr_raw.get("aggressive", {})),
                    "user_profile_type": pr_raw.get("user_profile_type", ""),
                    "user_recommendation": pr_raw.get("user_recommendation", ""),
                }

            return {
                "sections": sections,
                "scenario_forecast": scenario_forecast,
                "profile_recommendations": profile_recommendations,
                "forecast_6months": str(data_out.get("forecast_6months") or ""),
                "buy_recommendation": str(data_out.get("buy_recommendation") or ""),
                "signal": signal,
                "signal_score": round(signal_score, 2),
                "signal_blocks": signal_blocks,
            }
        except Exception as e:
            logger.error(f"Ошибка get_btc_analysis: {e}")
            return {
                "error": "Не удалось выполнить анализ. Попробуйте позже.",
                "sections": [],
                "scenario_forecast": None,
                "profile_recommendations": None,
                "forecast_6months": "",
                "buy_recommendation": "",
                "signal": "HOLD",
                "signal_score": 0.0,
                "signal_blocks": {},
            }
    
    def process_quick_command(self, command: str) -> Optional[str]:
        """Обработать быструю команду."""
        command_lower = command.lower().strip()
        
        # Проверяем точное совпадение
        if command_lower in self.QUICK_COMMANDS:
            return self.QUICK_COMMANDS[command_lower]
        
        # Проверяем, начинается ли с /
        if command_lower.startswith('/'):
            cmd = command_lower[1:]
            if cmd in self.QUICK_COMMANDS:
                return self.QUICK_COMMANDS[cmd]
        
        return None
    
    def get_recommendation(self, session_id: str, message: str) -> str:
        """
        Получить рекомендацию от ИИ.
        
        Args:
            session_id: ID сессии пользователя
            message: Сообщение пользователя
            
        Returns:
            Ответ ИИ
        """
        
        # Проверяем быстрые команды
        quick_message = self.process_quick_command(message)
        
        # Специальная обработка команды rebalance
        if quick_message == '__REBALANCE_COMMAND__':
            return self.get_rebalance_suggestion(session_id)
        
        if quick_message:
            message = quick_message
        
        # Получаем системный промпт
        system_prompt = self.get_system_prompt(session_id)
        
        # Добавляем контекст рынка
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        market_context = self.get_market_context(portfolio)
        system_prompt += market_context
        
        # Получаем историю сообщений (последние 10)
        history = ChatMessage.objects.filter(
            session_id=session_id
        ).order_by('-created_at')[:10]
        
        # Формируем сообщения для API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Добавляем историю (в правильном порядке)
        for msg in reversed(list(history)):
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Добавляем текущее сообщение
        messages.append({"role": "user", "content": message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1500,
                temperature=0.7,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка OpenAI API: {e}")
            return (
                "Извините, произошла ошибка при обработке запроса. "
                "Пожалуйста, попробуйте позже или переформулируйте вопрос."
            )
    
    def get_portfolio_summary(self, session_id: str) -> str:
        """Генерирует краткую сводку по портфелю."""
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return "У вас пока нет активного портфеля. Создайте портфель, чтобы получать рекомендации."
        
        message = """Дай краткую сводку по моему портфелю:
1. Текущее состояние (стоимость, прибыль/убыток)
2. Краткий анализ каждого актива
3. Общая оценка ситуации на рынке
4. Рекомендация: держать / докупать / частично фиксировать

Ответь кратко и по делу."""
        
        return self.get_recommendation(session_id, message)
    
    def analyze_risk(self, session_id: str) -> Dict:
        """Анализирует риски портфеля."""
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return {
                'error': 'Портфель не найден',
                'risk_level': None,
                'analysis': None
            }
        
        # Получаем профиль по session_id
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
            max_drawdown = profile.max_drawdown
        except InvestorProfile.DoesNotExist:
            max_drawdown = 30  # По умолчанию
        
        analyzer = PortfolioAnalyzer(portfolio)
        value_data = analyzer.get_current_value()
        drawdown_data = analyzer.get_drawdown()
        time_data = analyzer.get_time_metrics()
        
        current_drawdown = drawdown_data['current_drawdown']
        
        # Определяем уровень риска
        if current_drawdown < max_drawdown * 0.5:
            risk_level = 'low'
            risk_label = 'Низкий'
            risk_emoji = '🟢'
        elif current_drawdown < max_drawdown * 0.8:
            risk_level = 'medium'
            risk_label = 'Средний'
            risk_emoji = '🟡'
        elif current_drawdown < max_drawdown:
            risk_level = 'elevated'
            risk_label = 'Повышенный'
            risk_emoji = '🟠'
        else:
            risk_level = 'high'
            risk_label = 'Высокий'
            risk_emoji = '🔴'
        
        # Формируем рекомендации
        recommendations = []
        
        if risk_level == 'low':
            recommendations.append('Портфель в хорошем состоянии. Продолжайте следовать стратегии.')
        elif risk_level == 'medium':
            recommendations.append('Волатильность в пределах нормы. Рекомендуется держать позиции.')
        elif risk_level == 'elevated':
            recommendations.append('Просадка приближается к допустимому уровню. Следите за рынком.')
            recommendations.append('Возможно, стоит приостановить докупки до стабилизации.')
        else:
            recommendations.append('Просадка превысила допустимый уровень!')
            recommendations.append('Рассмотрите частичный перевод в стейблкоины (10-20%).')
            recommendations.append('НЕ продавайте всё в панике — это может зафиксировать убытки.')
        
        return {
            'risk_level': risk_level,
            'risk_label': risk_label,
            'risk_emoji': risk_emoji,
            'current_drawdown': round(current_drawdown, 2),
            'max_allowed_drawdown': max_drawdown,
            'drawdown_usage': round(current_drawdown / max_drawdown * 100, 1) if max_drawdown > 0 else 0,
            'portfolio_value': round(value_data['current_value'], 2),
            'profit_loss_percent': round(value_data['profit_loss_percent'], 2),
            'days_active': time_data['days_active'],
            'recommendations': recommendations,
        }
    
    def get_drawdown_alert(self, session_id: str) -> Optional[Dict]:
        """Проверяет, нужно ли отправить алерт о просадке."""
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return None
        
        # Получаем профиль по session_id
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
            max_drawdown = profile.max_drawdown
        except InvestorProfile.DoesNotExist:
            return None
        
        analyzer = PortfolioAnalyzer(portfolio)
        drawdown_data = analyzer.get_drawdown()
        current_drawdown = drawdown_data['current_drawdown']
        
        if current_drawdown >= max_drawdown:
            return {
                'alert': True,
                'level': 'critical',
                'message': f'⚠️ Просадка портфеля ({current_drawdown:.1f}%) превысила допустимый уровень ({max_drawdown}%)!',
                'current_drawdown': current_drawdown,
                'max_drawdown': max_drawdown,
            }
        elif current_drawdown >= max_drawdown * 0.8:
            return {
                'alert': True,
                'level': 'warning',
                'message': f'⚡ Внимание: просадка портфеля ({current_drawdown:.1f}%) приближается к допустимому уровню ({max_drawdown}%).',
                'current_drawdown': current_drawdown,
                'max_drawdown': max_drawdown,
            }
        
        return None
    
    def get_rebalance_suggestion(self, session_id: str) -> str:
        """
        Генерирует предложение по реструктуризации портфеля.
        Возвращает структурированный ответ с JSON-данными для модального окна.
        """
        import json
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return "У вас пока нет активного портфеля. Создайте портфель, чтобы получать рекомендации по реструктуризации."
        
        # Получаем текущие активы (конвертируем Decimal в float для JSON)
        current_assets = [
            {
                'symbol': asset.symbol,
                'name': asset.name,
                'percentage': float(asset.percentage)
            }
            for asset in portfolio.assets.all()
        ]
        
        # Анализируем портфель
        analyzer = PortfolioAnalyzer(portfolio)
        value_data = analyzer.get_current_value()
        
        # Формируем промпт для AI с просьбой предложить реструктуризацию
        rebalance_prompt = f"""Проанализируй текущий портфель и предложи оптимальную реструктуризацию.

ТЕКУЩИЙ СОСТАВ ПОРТФЕЛЯ:
{json.dumps(current_assets, ensure_ascii=False, indent=2)}

ВАЖНО: Реструктуризация требует уплаты комиссий за продажу, покупку и конвертацию активов.
Рекомендуй реструктуризацию ТОЛЬКО при значительных изменениях на крипторынке (резкий сдвиг капитализации, выход новых лидеров, серьёзные макро-события).
При незначительных отклонениях от целевого распределения — рекомендуй держать текущий состав или докупать при следующем DCA-взносе.

ТРЕБОВАНИЯ К ОТВЕТУ:
1. Проанализируй текущее распределение и рыночную ситуацию
2. Предложи новое распределение активов (сумма процентов = 100%) — только если изменения на рынке существенны
3. Объясни причины изменений
4. В КОНЦЕ ответа ОБЯЗАТЕЛЬНО добавь блок с JSON в формате:

[REBALANCE_SUGGESTION]
{{"newAssets": [
  {{"symbol": "BTC", "name": "Bitcoin", "percentage": 50}},
  {{"symbol": "ETH", "name": "Ethereum", "percentage": 30}},
  ...
]}}
[/REBALANCE_SUGGESTION]

ВАЖНО: Блок [REBALANCE_SUGGESTION] должен содержать ТОЛЬКО валидный JSON с массивом newAssets!
Каждый актив должен иметь: symbol, name, percentage.
Сумма всех percentage должна быть ровно 100.

Используй только поддерживаемые активы: BTC, ETH, BNB, SOL, ADA, XRP, DOGE, DOT, MATIC, LINK, AVAX, ATOM, LTC, UNI, SHIB, TRX, USDT, USDC.
"""
        
        # Получаем системный промпт
        system_prompt = self.get_system_prompt(session_id)
        market_context = self.get_market_context(portfolio)
        system_prompt += market_context
        
        # Формируем сообщения для API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": rebalance_prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка OpenAI API при реструктуризации: {e}")
            return (
                "Извините, произошла ошибка при анализе портфеля для реструктуризации. "
                "Пожалуйста, попробуйте позже."
            )
    
    @classmethod
    def get_quick_commands(cls) -> Dict[str, str]:
        """Получить список быстрых команд."""
        return cls.QUICK_COMMANDS.copy()
