from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date

from .models import Portfolio, PortfolioAsset
from .serializers import (
    PortfolioSerializer,
    PortfolioCreateSerializer,
)
from .services import PriceService


class PortfolioListCreateView(APIView):
    """Список портфелей и создание нового."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить список портфелей по session_id."""
        portfolios = Portfolio.objects.filter(session_id=request.session_id)
        serializer = PortfolioSerializer(portfolios, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Создать новый портфель."""
        session_id = request.session_id
        
        # Проверяем, есть ли уже активный портфель
        active_portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        if active_portfolio:
            return Response(
                {'detail': 'У вас уже есть активный портфель. Деактивируйте его перед созданием нового.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PortfolioCreateSerializer(data=request.data)
        if serializer.is_valid():
            portfolio = serializer.save(session_id=session_id)
            return Response(
                PortfolioSerializer(portfolio).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PortfolioDetailView(APIView):
    """Детали портфеля."""
    permission_classes = (AllowAny,)
    
    def get_portfolio(self, request, pk):
        try:
            return Portfolio.objects.get(pk=pk, session_id=request.session_id)
        except Portfolio.DoesNotExist:
            return None
    
    def get(self, request, pk):
        """Получить детали портфеля."""
        portfolio = self.get_portfolio(request, pk)
        if not portfolio:
            return Response(
                {'detail': 'Портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = PortfolioSerializer(portfolio)
        return Response(serializer.data)
    
    def patch(self, request, pk):
        """Обновить портфель."""
        portfolio = self.get_portfolio(request, pk)
        if not portfolio:
            return Response(
                {'detail': 'Портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PortfolioSerializer(
            portfolio,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Деактивировать портфель."""
        portfolio = self.get_portfolio(request, pk)
        if not portfolio:
            return Response(
                {'detail': 'Портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        portfolio.is_active = False
        portfolio.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortfolioValueView(APIView):
    """Текущая стоимость портфеля."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить текущую стоимость активного портфеля."""
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Получаем активы
        assets = portfolio.assets.all()
        symbols = [asset.symbol for asset in assets]
        
        # Получаем текущие цены с изменениями
        price_service = PriceService()
        price_data = price_service.get_prices_with_changes(symbols)
        
        # Рассчитываем стоимость
        initial_value = float(portfolio.initial_amount)
        total_value = 0
        assets_data = []
        
        for asset in assets:
            symbol_data = price_data.get(asset.symbol, {})
            current_price = symbol_data.get('price', 0)
            change_24h = symbol_data.get('change_24h', 0)
            
            asset_initial_value = initial_value * float(asset.percentage) / 100
            
            # Если есть начальная цена, рассчитываем реальную стоимость
            if asset.initial_price and current_price:
                # Количество единиц актива
                units = asset_initial_value / float(asset.initial_price)
                asset_current_value = units * current_price
            else:
                # Если нет начальной цены, показываем начальное распределение
                asset_current_value = asset_initial_value
            
            total_value += asset_current_value
            
            profit_loss = asset_current_value - asset_initial_value
            profit_loss_percent = (
                (profit_loss / asset_initial_value * 100)
                if asset_initial_value > 0 else 0
            )
            
            assets_data.append({
                'symbol': asset.symbol,
                'name': asset.name,
                'percentage': float(asset.percentage),
                'initial_value': round(asset_initial_value, 2),
                'current_value': round(asset_current_value, 2),
                'initial_price': float(asset.initial_price) if asset.initial_price else None,
                'current_price': current_price,
                'change_24h': round(change_24h, 2),
                'profit_loss': round(profit_loss, 2),
                'profit_loss_percent': round(profit_loss_percent, 2),
            })
        
        # Расчёт общей прибыли/убытка
        profit_loss = total_value - initial_value
        profit_loss_percent = (profit_loss / initial_value * 100) if initial_value > 0 else 0
        
        # Дней до целевой даты
        today = date.today()
        target_date = portfolio.target_date
        days_remaining = (target_date - today).days if target_date > today else 0
        
        # Дней с начала
        days_active = (today - portfolio.start_date).days
        
        response_data = {
            'portfolio_id': portfolio.id,
            'portfolio_name': portfolio.name,
            'total_value': round(total_value, 2),
            'initial_value': round(initial_value, 2),
            'profit_loss': round(profit_loss, 2),
            'profit_loss_percent': round(profit_loss_percent, 2),
            'start_date': portfolio.start_date,
            'target_date': target_date,
            'target_years': portfolio.target_years,
            'days_active': days_active,
            'days_remaining': days_remaining,
            'assets': assets_data,
        }
        
        return Response(response_data)


class ActivePortfolioView(APIView):
    """Получение активного портфеля."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить активный портфель по session_id."""
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден. Создайте портфель.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PortfolioSerializer(portfolio)
        return Response(serializer.data)


class RebalancePortfolioView(APIView):
    """Ребалансировка портфеля - обновление активов."""
    permission_classes = (AllowAny,)
    
    def post(self, request):
        """
        Обновить активы портфеля (ребалансировка).
        
        Body:
            assets: [
                { "symbol": "BTC", "name": "Bitcoin", "percentage": 50 },
                { "symbol": "ETH", "name": "Ethereum", "percentage": 30 },
                ...
            ]
        """
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()
        
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        assets_data = request.data.get('assets', [])
        
        if not assets_data:
            return Response(
                {'detail': 'Список активов не может быть пустым.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверка суммы процентов
        total_percentage = sum(asset.get('percentage', 0) for asset in assets_data)
        if abs(total_percentage - 100) > 0.01:
            return Response(
                {'detail': f'Сумма процентов должна быть 100%, получено: {total_percentage}%'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Сохраняем старые initial_price, чтобы не потерять историю
        old_initial_prices = {
            asset.symbol: float(asset.initial_price) if asset.initial_price else None
            for asset in portfolio.assets.all()
        }
        
        # Получаем текущие цены для НОВЫХ активов
        price_service = PriceService()
        symbols = [asset.get('symbol', '').upper() for asset in assets_data]
        current_prices = price_service.get_prices(symbols)
        
        # Удаляем старые активы
        portfolio.assets.all().delete()
        
        # Создаём новые активы
        new_assets = []
        for asset_data in assets_data:
            symbol = asset_data.get('symbol', '').upper()
            name = asset_data.get('name', symbol)
            percentage = asset_data.get('percentage', 0)
            
            # Для существующих активов сохраняем старую initial_price
            # Для новых активов используем текущую цену
            if symbol in old_initial_prices and old_initial_prices[symbol]:
                initial_price = old_initial_prices[symbol]
            else:
                initial_price = current_prices.get(symbol, 0)
            
            asset = PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol=symbol,
                name=name,
                percentage=percentage,
                initial_price=initial_price
            )
            new_assets.append({
                'symbol': asset.symbol,
                'name': asset.name,
                'percentage': float(asset.percentage),
            })
        
        return Response({
            'success': True,
            'message': 'Портфель успешно обновлён',
            'assets': new_assets,
        })


# ============ Views для цен ============

class PricesView(APIView):
    """Получение текущих цен криптовалют."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить текущие цены.
        
        Query params:
            symbols: Символы через запятую (например: BTC,ETH,SOL)
                     Если не указано, возвращает все поддерживаемые
        """
        symbols_param = request.query_params.get('symbols', '')
        
        price_service = PriceService()
        
        if symbols_param:
            # Парсим символы из параметра
            symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()]
        else:
            # Возвращаем все поддерживаемые
            symbols = PriceService.get_supported_symbols()
        
        prices = price_service.get_prices(symbols)
        
        # Форматируем ответ
        result = [
            {'symbol': symbol, 'price': price}
            for symbol, price in prices.items()
        ]
        
        return Response({
            'prices': result,
            'count': len(result),
        })


class PricesWithChangesView(APIView):
    """Получение цен с изменениями за 24 часа."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить цены с изменениями за 24ч.
        
        Query params:
            symbols: Символы через запятую
        """
        symbols_param = request.query_params.get('symbols', '')
        
        price_service = PriceService()
        
        if symbols_param:
            symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()]
        else:
            symbols = PriceService.get_supported_symbols()
        
        price_data = price_service.get_prices_with_changes(symbols)
        
        result = [
            {
                'symbol': symbol,
                'price': data['price'],
                'change_24h': round(data['change_24h'], 2),
            }
            for symbol, data in price_data.items()
        ]
        
        return Response({
            'prices': result,
            'count': len(result),
        })


class MarketDataView(APIView):
    """Получение расширенных рыночных данных."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """
        Получить рыночные данные (капитализация, объёмы, изменения).
        
        Query params:
            symbols: Символы через запятую
        """
        symbols_param = request.query_params.get('symbols', '')
        
        price_service = PriceService()
        
        if symbols_param:
            symbols = [s.strip().upper() for s in symbols_param.split(',') if s.strip()]
        else:
            # Для рыночных данных по умолчанию топ-5
            symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP']
        
        market_data = price_service.get_market_data(symbols)
        
        result = [
            {'symbol': symbol, **data}
            for symbol, data in market_data.items()
        ]
        
        # Сортируем по капитализации
        result.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
        
        return Response({
            'market_data': result,
            'count': len(result),
        })


class HistoricalPricesView(APIView):
    """Получение исторических цен."""
    permission_classes = (AllowAny,)
    
    def get(self, request, symbol):
        """
        Получить исторические цены актива.
        
        Path params:
            symbol: Символ криптовалюты (BTC, ETH, ...)
            
        Query params:
            days: Количество дней (по умолчанию 30, максимум 365)
        """
        symbol = symbol.upper()
        
        if not PriceService.is_symbol_supported(symbol):
            return Response(
                {'detail': f"Символ '{symbol}' не поддерживается."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        days = min(days, 365)  # Ограничиваем максимум
        
        price_service = PriceService()
        history = price_service.get_historical_prices(symbol, days)
        
        return Response({
            'symbol': symbol,
            'days': days,
            'history': history,
            'count': len(history),
        })


class SupportedAssetsView(APIView):
    """Получение списка поддерживаемых активов."""
    permission_classes = (AllowAny,)
    
    def get(self, request):
        """Получить список поддерживаемых символов."""
        symbols = PriceService.get_supported_symbols()
        
        return Response({
            'symbols': symbols,
            'count': len(symbols),
        })
