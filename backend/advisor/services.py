"""
Сервис ИИ-консультанта.
"""

from openai import OpenAI
from django.conf import settings
from typing import Optional, Dict, List
from datetime import date, timedelta
from decimal import Decimal
import logging

from portfolios.models import Portfolio
from portfolios.services import PriceService
from users.models import InvestorProfile
from .models import ChatMessage

logger = logging.getLogger(__name__)


class PortfolioAnalyzer:
    """Анализатор портфеля для расчёта метрик."""
    
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.price_service = PriceService()
    
    def get_current_value(self) -> Dict:
        """Рассчитать текущую стоимость портфеля."""
        assets = self.portfolio.assets.all()
        symbols = [asset.symbol for asset in assets]
        
        price_data = self.price_service.get_prices_with_changes(symbols)
        
        initial_value = float(self.portfolio.initial_amount)
        total_value = 0
        assets_info = []
        
        for asset in assets:
            symbol_data = price_data.get(asset.symbol, {})
            current_price = symbol_data.get('price', 0)
            change_24h = symbol_data.get('change_24h', 0)
            
            asset_initial_value = initial_value * float(asset.percentage) / 100
            
            if asset.initial_price and current_price:
                units = asset_initial_value / float(asset.initial_price)
                asset_current_value = units * current_price
            else:
                asset_current_value = asset_initial_value
            
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
                'initial_value': asset_initial_value,
                'current_value': asset_current_value,
                'current_price': current_price,
                'change_24h': change_24h,
                'profit_loss': profit_loss,
                'profit_loss_percent': profit_loss_percent,
            })
        
        profit_loss = total_value - initial_value
        profit_loss_percent = (profit_loss / initial_value * 100) if initial_value > 0 else 0
        
        return {
            'initial_value': initial_value,
            'current_value': total_value,
            'profit_loss': profit_loss,
            'profit_loss_percent': profit_loss_percent,
            'assets': assets_info,
        }
    
    def get_drawdown(self) -> Dict:
        """
        Рассчитать текущую просадку.
        Просадка = (пиковое значение - текущее значение) / пиковое значение * 100
        """
        value_data = self.get_current_value()
        initial_value = value_data['initial_value']
        current_value = value_data['current_value']
        
        # Для MVP используем начальную стоимость как пиковую
        # В полной версии нужно хранить историю и находить реальный пик
        peak_value = max(initial_value, current_value)
        
        if current_value >= peak_value:
            drawdown = 0
        else:
            drawdown = (peak_value - current_value) / peak_value * 100
        
        return {
            'current_drawdown': drawdown,
            'peak_value': peak_value,
            'current_value': current_value,
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
            raise ValueError("OPENAI_API_KEY не настроен в settings")
        
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
            
            prompt += f"""
═══════════════════════════════════════
ТЕКУЩИЙ ПОРТФЕЛЬ:
═══════════════════════════════════════
• Название: {portfolio.name}
• Дата начала: {portfolio.start_date}
• Целевой горизонт: {portfolio.target_years} лет
• Целевая дата: {time_data['target_date']}
• Дней активен: {time_data['days_active']}
• Дней осталось: {time_data['days_remaining']}
• Прогресс: {time_data['progress_percent']:.1f}%

💰 ФИНАНСЫ:
• Начальная сумма: ${value_data['initial_value']:,.2f}
• Текущая стоимость: ${value_data['current_value']:,.2f}
• Прибыль/убыток: {profit_emoji} ${value_data['profit_loss']:+,.2f} ({value_data['profit_loss_percent']:+.1f}%)
• Текущая просадка: {drawdown_data['current_drawdown']:.1f}%

📊 СОСТАВ ПОРТФЕЛЯ:
{assets_str}
"""
            
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
        print(f"[DEBUG] Загружены цены для {len(price_data)} монет: {list(price_data.keys())}")
        
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
        Генерирует предложение по ребалансировке портфеля.
        Возвращает структурированный ответ с JSON-данными для модального окна.
        """
        import json
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return "У вас пока нет активного портфеля. Создайте портфель, чтобы получать рекомендации по ребалансировке."
        
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
        
        # Формируем промпт для AI с просьбой предложить ребалансировку
        rebalance_prompt = f"""Проанализируй текущий портфель и предложи оптимальную ребалансировку.

ТЕКУЩИЙ СОСТАВ ПОРТФЕЛЯ:
{json.dumps(current_assets, ensure_ascii=False, indent=2)}

ТРЕБОВАНИЯ К ОТВЕТУ:
1. Проанализируй текущее распределение и рыночную ситуацию
2. Предложи новое распределение активов (сумма процентов = 100%)
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
            logger.error(f"Ошибка OpenAI API при ребалансировке: {e}")
            return (
                "Извините, произошла ошибка при анализе портфеля для ребалансировки. "
                "Пожалуйста, попробуйте позже."
            )
    
    @classmethod
    def get_quick_commands(cls) -> Dict[str, str]:
        """Получить список быстрых команд."""
        return cls.QUICK_COMMANDS.copy()
