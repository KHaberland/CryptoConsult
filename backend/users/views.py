from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date

from .serializers import InvestorProfileSerializer
from .models import InvestorProfile
from portfolios.models import Portfolio
from portfolios.services import PriceService


class ProfileLookupView(APIView):
    """Поиск профиля по имени (для MVP без регистрации)."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Найти профиль по имени.
        
        Query params:
            name: Имя пользователя
        
        Returns:
            200: Профиль найден + данные портфеля + анализ
            404: Профиль не найден
        """
        name = request.query_params.get('name', '').strip()
        
        if not name:
            return Response(
                {'detail': 'Параметр name обязателен.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profile = InvestorProfile.objects.get(name__iexact=name)
        except InvestorProfile.DoesNotExist:
            return Response(
                {'detail': 'Пользователь не найден.', 'exists': False},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Получаем портфель
        portfolio = Portfolio.objects.filter(
            session_id=profile.session_id,
            is_active=True
        ).first()
        
        portfolio_data = None
        analysis = None
        
        if portfolio:
            # Рассчитываем текущую стоимость
            assets = portfolio.assets.all()
            symbols = [asset.symbol for asset in assets]
            
            price_service = PriceService()
            price_data = price_service.get_prices(symbols)
            
            initial_value = float(portfolio.initial_amount)
            current_value = 0
            
            for asset in assets:
                current_price = price_data.get(asset.symbol, 0)
                asset_initial_value = initial_value * float(asset.percentage) / 100
                
                if asset.initial_price and current_price:
                    units = asset_initial_value / float(asset.initial_price)
                    asset_current_value = units * current_price
                else:
                    asset_current_value = asset_initial_value
                
                current_value += asset_current_value
            
            profit_loss = current_value - initial_value
            profit_loss_percent = (profit_loss / initial_value * 100) if initial_value > 0 else 0
            
            # Дней с момента создания
            days_active = (date.today() - portfolio.start_date).days
            
            portfolio_data = {
                'name': portfolio.name,
                'start_date': portfolio.start_date.isoformat(),
                'initial_value': round(initial_value, 2),
                'current_value': round(current_value, 2),
                'profit_loss': round(profit_loss, 2),
                'profit_loss_percent': round(profit_loss_percent, 2),
                'days_active': days_active,
            }
            
            # Генерируем анализ
            max_drawdown = profile.max_drawdown
            
            if profit_loss_percent >= 0:
                # Прибыль
                analysis = {
                    'status': 'profit',
                    'icon': '📈',
                    'title': f'Прибыль: +{profit_loss_percent:.1f}%',
                    'message': f'🎉 Поздравляем! Ваш портфель вырос на {profit_loss_percent:.1f}%!',
                    'recommendation': 'Отличный результат! Продолжайте следовать стратегии.'
                }
            else:
                # Просадка
                drawdown = abs(profit_loss_percent)
                drawdown_ratio = drawdown / max_drawdown if max_drawdown > 0 else 0
                
                if drawdown_ratio < 0.8:
                    # Просадка в норме
                    analysis = {
                        'status': 'normal',
                        'icon': '📉',
                        'title': f'Просадка: -{drawdown:.1f}%',
                        'message': f'✅ Величина просадки укладывается в допустимый уровень ({max_drawdown}%).',
                        'recommendation': 'Продолжайте придерживаться стратегии. Краткосрочные колебания — это норма.'
                    }
                elif drawdown_ratio < 1.0:
                    # Приближается к лимиту
                    analysis = {
                        'status': 'warning',
                        'icon': '⚠️',
                        'title': f'Просадка: -{drawdown:.1f}%',
                        'message': f'⚠️ Внимание! Просадка приближается к допустимому уровню ({max_drawdown}%).',
                        'recommendation': 'Следите за рынком внимательнее. Возможно, стоит приостановить докупки.'
                    }
                else:
                    # Превышает лимит
                    analysis = {
                        'status': 'critical',
                        'icon': '🔴',
                        'title': f'Просадка: -{drawdown:.1f}%',
                        'message': f'🔴 Просадка превысила допустимый уровень ({max_drawdown}%)!',
                        'recommendation': 'Рассмотрите частичный перевод в стейблкоины (10-20%). НЕ продавайте всё в панике.'
                    }
        
        return Response({
            'exists': True,
            'session_id': profile.session_id,
            'name': profile.name,
            'created_at': profile.created_at.isoformat(),
            'portfolio': portfolio_data,
            'analysis': analysis,
        })


class InvestorProfileView(APIView):
    """Профиль инвестора (анкета). Работает по session_id."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить профиль инвестора по session_id."""
        session_id = request.session_id
        
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
            serializer = InvestorProfileSerializer(profile)
            return Response(serializer.data)
        except InvestorProfile.DoesNotExist:
            return Response(
                {'detail': 'Профиль инвестора не найден. Заполните анкету.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
        """Создать профиль инвестора."""
        session_id = request.session_id
        
        # Проверяем, есть ли уже профиль
        if InvestorProfile.objects.filter(session_id=session_id).exists():
            return Response(
                {'detail': 'Профиль уже существует. Используйте PATCH для обновления.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = InvestorProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(session_id=session_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        """Обновить профиль инвестора."""
        session_id = request.session_id
        
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
        except InvestorProfile.DoesNotExist:
            return Response(
                {'detail': 'Профиль не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = InvestorProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
