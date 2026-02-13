from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from portfolios.models import Portfolio
from users.models import InvestorProfile
from .models import ChatMessage
from .serializers import (
    ChatMessageSerializer,
    ChatInputSerializer,
)
from .services import AIAdvisorService


class ChatView(APIView):
    """Чат с ИИ-консультантом."""
    permission_classes = (AllowAny,)
    
    def post(self, request):
        """
        Отправить сообщение и получить ответ.
        
        Поддерживает быстрые команды:
        - /status — статус портфеля
        - /recommendation — рекомендация
        - /risk — анализ рисков
        - /market — ситуация на рынке
        - /drawdown — анализ просадки
        - /rebalance — нужна ли реструктуризация
        - /dca — когда делать следующую покупку
        - /exit — стоит ли фиксировать прибыль
        """
        session_id = request.session_id
        
        serializer = ChatInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        message = serializer.validated_data['message']
        
        # Получаем активный портфель (если есть)
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        # Сохраняем сообщение пользователя
        user_message = ChatMessage.objects.create(
            session_id=session_id,
            role='user',
            content=message,
            portfolio=portfolio
        )
        
        try:
            # Получаем ответ от ИИ
            advisor = AIAdvisorService()
            response_text = advisor.get_recommendation(session_id, message)
            
            # Сохраняем ответ ИИ
            assistant_message = ChatMessage.objects.create(
                session_id=session_id,
                role='assistant',
                content=response_text,
                portfolio=portfolio
            )
            
            # Проверяем алерт о просадке
            drawdown_alert = advisor.get_drawdown_alert(session_id)
            
            response_data = {
                'response': response_text,
                'user_message': ChatMessageSerializer(user_message).data,
                'assistant_message': ChatMessageSerializer(assistant_message).data,
            }
            
            if drawdown_alert:
                response_data['alert'] = drawdown_alert
            
            return Response(response_data)
            
        except ValueError as e:
            # Ошибка конфигурации (нет API ключа)
            # Удаляем сообщение пользователя, так как ответ не получен
            user_message.delete()
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            user_message.delete()
            return Response(
                {'detail': 'Произошла ошибка при обработке запроса.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatHistoryView(APIView):
    """История чата."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить историю сообщений.
        
        Query params:
            limit: Количество сообщений (по умолчанию 50, макс 100)
            offset: Смещение для пагинации
        """
        session_id = request.session_id
        
        # Параметры пагинации
        try:
            limit = int(request.query_params.get('limit', 50))
            offset = int(request.query_params.get('offset', 0))
        except ValueError:
            limit = 50
            offset = 0
        
        # Ограничиваем максимум
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)
        
        messages = ChatMessage.objects.filter(
            session_id=session_id
        ).order_by('-created_at')[offset:offset + limit]
        
        # Возвращаем в хронологическом порядке
        messages = list(reversed(messages))
        
        serializer = ChatMessageSerializer(messages, many=True)
        
        # Общее количество сообщений
        total = ChatMessage.objects.filter(session_id=session_id).count()
        
        return Response({
            'messages': serializer.data,
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total,
        })
    
    def delete(self, request):
        """Очистить историю чата."""
        session_id = request.session_id
        deleted_count = ChatMessage.objects.filter(session_id=session_id).count()
        ChatMessage.objects.filter(session_id=session_id).delete()
        return Response({
            'detail': f'Удалено {deleted_count} сообщений.',
            'deleted_count': deleted_count,
        })


class PortfolioSummaryView(APIView):
    """Получить сводку по портфелю от ИИ."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить краткую сводку по портфелю."""
        session_id = request.session_id
        
        # Проверяем наличие портфеля
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден. Создайте портфель.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            advisor = AIAdvisorService()
            summary = advisor.get_portfolio_summary(session_id)
            
            # Сохраняем как сообщения
            ChatMessage.objects.create(
                session_id=session_id,
                role='user',
                content='Дай краткую сводку по моему портфелю',
                portfolio=portfolio
            )
            
            ChatMessage.objects.create(
                session_id=session_id,
                role='assistant',
                content=summary,
                portfolio=portfolio
            )
            
            # Проверяем алерт о просадке
            drawdown_alert = advisor.get_drawdown_alert(session_id)
            
            response_data = {'summary': summary}
            if drawdown_alert:
                response_data['alert'] = drawdown_alert
            
            return Response(response_data)
            
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RiskAnalysisView(APIView):
    """Анализ рисков портфеля."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить анализ рисков портфеля.
        
        Возвращает:
        - Уровень риска (low/medium/elevated/high)
        - Текущую просадку
        - Рекомендации
        """
        session_id = request.session_id
        
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            advisor = AIAdvisorService()
            risk_analysis = advisor.analyze_risk(session_id)
            
            if 'error' in risk_analysis:
                return Response(
                    {'detail': risk_analysis['error']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(risk_analysis)
            
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DrawdownAlertView(APIView):
    """Проверка алерта о просадке."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Проверить, есть ли алерт о просадке.
        
        Возвращает алерт, если просадка:
        - >= 80% от допустимой (warning)
        - >= 100% от допустимой (critical)
        """
        session_id = request.session_id
        
        try:
            advisor = AIAdvisorService()
            alert = advisor.get_drawdown_alert(session_id)
            
            if alert:
                return Response(alert)
            else:
                return Response({
                    'alert': False,
                    'message': 'Просадка в пределах нормы.',
                })
                
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarketForecastView(APIView):
    """Прогноз крипторынка на 6 месяцев (3 сценария)."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить анализ крипторынка на 6 месяцев вперёд.
        
        Возвращает 3 сценария с вероятностями:
        - positive: позитивный сценарий
        - negative: негативный сценарий
        - base: базовый сценарий
        """
        try:
            advisor = AIAdvisorService()
            forecast = advisor.get_market_forecast_6m()
            return Response(forecast)
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'detail': 'Не удалось получить прогноз рынка.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QuickCommandsView(APIView):
    """Список быстрых команд."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить список доступных быстрых команд.
        
        Быстрые команды можно использовать в чате:
        - Отправить команду напрямую (например: "status")
        - Использовать с / (например: "/status")
        """
        
        commands = AIAdvisorService.get_quick_commands()
        
        commands_list = [
            {
                'command': cmd,
                'slash_command': f'/{cmd}',
                'description': desc,
            }
            for cmd, desc in commands.items()
        ]
        
        return Response({
            'commands': commands_list,
            'count': len(commands_list),
            'usage': 'Отправьте команду в чат (например: /status или просто status)',
        })
