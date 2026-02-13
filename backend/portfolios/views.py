from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date

from .models import Portfolio, PortfolioAsset, PortfolioContribution
from .serializers import (
    PortfolioSerializer,
    PortfolioCreateSerializer,
)
from .services import PriceService
from advisor.services import PortfolioAnalyzer


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
        
        analyzer = PortfolioAnalyzer(portfolio)
        value_data = analyzer.get_current_value()
        
        # Форматируем активы
        assets_data = []
        for asset in value_data['assets']:
            assets_data.append({
                'symbol': asset['symbol'],
                'name': asset['name'],
                'percentage': float(asset['percentage']),
                'initial_value': round(asset['initial_value'], 2),
                'current_value': round(asset['current_value'], 2),
                'current_price': asset['current_price'],
                'change_24h': round(asset['change_24h'], 2),
                'profit_loss': round(asset['profit_loss'], 2),
                'profit_loss_percent': round(asset['profit_loss_percent'], 2),
            })
        
        # Список взносов
        contributions = [
            {
                'id': c.id,
                'amount': float(c.amount),
                'contributed_at': c.contributed_at,
            }
            for c in portfolio.contributions.all().order_by('contributed_at')
        ]
        
        today = date.today()
        target_date = portfolio.target_date
        days_remaining = (target_date - today).days if target_date > today else 0
        days_active = (today - portfolio.start_date).days
        
        response_data = {
            'portfolio_id': portfolio.id,
            'portfolio_name': portfolio.name,
            'total_value': round(value_data['current_value'], 2),
            'initial_value': round(value_data['initial_value'], 2),
            'profit_loss': round(value_data['profit_loss'], 2),
            'profit_loss_percent': round(value_data['profit_loss_percent'], 2),
            'start_date': portfolio.start_date,
            'target_date': target_date,
            'target_years': portfolio.target_years,
            'days_active': days_active,
            'days_remaining': days_remaining,
            'assets': assets_data,
            'contributions': contributions,
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


class ContributePortfolioView(APIView):
    """Внесение взноса в портфель (DCA)."""
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Внести взнос в активный портфель.

        Body:
            amount: сумма взноса в USD (например 1666)
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

        try:
            amount = float(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Укажите корректную сумму взноса.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {'detail': 'Сумма взноса должна быть больше нуля.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаём запись о взносе
        contribution = PortfolioContribution.objects.create(
            portfolio=portfolio,
            amount=amount
        )

        # Получаем текущие цены
        assets = portfolio.assets.all()
        symbols = [asset.symbol for asset in assets]
        price_service = PriceService()
        current_prices = price_service.get_prices(symbols)

        # Добавляем units к каждому активу
        for asset in assets:
            pct = float(asset.percentage)
            asset_value = amount * pct / 100
            price = current_prices.get(asset.symbol, 0) or float(asset.initial_price or 0)
            new_units = (asset_value / price) if price else 0

            if new_units > 0:
                old_units = float(asset.units or 0)
                if old_units <= 0:
                    # Инициализация для старых портфелей: units из initial_amount
                    init_val = float(portfolio.initial_amount) * pct / 100
                    init_price = float(asset.initial_price or 0) or price
                    old_units = (init_val / init_price) if init_price else 0
                asset.units = old_units + new_units
                asset.save(update_fields=['units'])

        return Response({
            'success': True,
            'message': f'Взнос ${amount:,.2f} успешно внесён.',
            'contribution': {
                'id': contribution.id,
                'amount': float(contribution.amount),
                'contributed_at': contribution.contributed_at,
            },
        }, status=status.HTTP_201_CREATED)


class WithdrawProposalView(APIView):
    """Предложение по выводу средств (пропорционально активам)."""
    permission_classes = (AllowAny,)

    def get(self, request):
        """
        Получить предложение по выводу.

        Query: amount — сумма в USD для вывода
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

        try:
            amount = float(request.query_params.get('amount', 0))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Укажите корректную сумму вывода.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {'detail': 'Сумма вывода должна быть больше нуля.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        analyzer = PortfolioAnalyzer(portfolio)
        value_data = analyzer.get_current_value()
        total_value = value_data['current_value']
        units_scale = analyzer.get_units_scale()

        if amount > total_value:
            return Response(
                {'detail': f'Сумма вывода ({amount:.2f}) превышает стоимость портфеля ({total_value:.2f}).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        price_service = PriceService()
        assets = portfolio.assets.all()
        symbols = [a.symbol for a in assets]
        prices = price_service.get_prices(symbols)

        proposal = []
        assets_data = value_data['assets']
        for i, asset in enumerate(assets_data):
            symbol = asset['symbol']
            current_value = asset['current_value']
            current_price = asset['current_price'] or prices.get(symbol, 0) or 0

            # units = current_value / price
            units_current = (current_value / current_price) if current_price else 0

            # Пропорциональная доля вывода
            share = (current_value / total_value) if total_value > 0 else 0
            value_to_sell = amount * share
            # Последний актив: корректируем для точной суммы (устраняет погрешности округления)
            if i == len(assets_data) - 1 and len(proposal) > 0:
                allocated = sum(p['value_usd'] for p in proposal)
                value_to_sell = max(0, min(amount - allocated, current_value))

            # units_to_sell — в RAW (для вычета из БД). При DCA scale < 1 display_units = raw * scale
            units_to_sell = (value_to_sell / current_price) if current_price else 0
            if units_scale > 0 and units_scale < 1:
                units_to_sell = units_to_sell / units_scale
            units_current_raw = units_current / units_scale if (units_scale > 0 and units_scale < 1) else units_current
            units_to_sell = min(units_to_sell, units_current_raw)

            # value_usd — сумма к выводу (для отображения пользователю), не units*price при scale
            value_usd = round(value_to_sell, 2)

            proposal.append({
                'symbol': symbol,
                'name': asset['name'],
                'units_current': round(units_current_raw, 8),
                'units_to_sell': round(units_to_sell, 8),
                'current_price': current_price,
                'value_usd': value_usd,
            })

        return Response({
            'amount': amount,
            'assets': proposal,
            'total_value': round(total_value, 2),
        })


class WithdrawPortfolioView(APIView):
    """Выполнение вывода средств из портфеля."""
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Вывести средства из портфеля.

        Body:
            assets: [
                { "symbol": "BTC", "units_to_sell": 0.01 },
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
                {'detail': 'Укажите активы для вывода.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        price_service = PriceService()
        assets_by_symbol = {a.symbol: a for a in portfolio.assets.all()}
        prices = price_service.get_prices(list(assets_by_symbol.keys()))

        for item in assets_data:
            symbol = item.get('symbol', '').upper()
            try:
                units_to_sell = float(item.get('units_to_sell', 0))
            except (TypeError, ValueError):
                units_to_sell = 0

            if units_to_sell <= 0:
                continue

            asset = assets_by_symbol.get(symbol)
            if not asset:
                continue

            units_current = float(asset.units or 0)
            if units_current <= 0:
                # Fallback для старых портфелей (как в PortfolioAnalyzer)
                asset_val = float(portfolio.initial_amount) * float(asset.percentage) / 100
                init_price = float(asset.initial_price or 0) or prices.get(symbol, 0)
                units_current = (asset_val / init_price) if init_price else 0

            units_to_sell = min(units_to_sell, units_current)
            if units_to_sell <= 0:
                continue

            new_units = units_current - units_to_sell
            asset.units = max(0, new_units)
            asset.save(update_fields=['units'])

        return Response({
            'success': True,
            'message': 'Вывод средств выполнен.',
        }, status=status.HTTP_200_OK)


class RebalancePortfolioView(APIView):
    """Реструктуризация портфеля - обновление активов."""
    permission_classes = (AllowAny,)
    
    def post(self, request):
        """
        Обновить активы портфеля (реструктуризация).
        
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
        
        # Сохраняем старые initial_price и считаем текущую стоимость до реструктуризации
        old_assets = list(portfolio.assets.all())
        old_initial_prices = {a.symbol: float(a.initial_price) if a.initial_price else None for a in old_assets}

        price_service = PriceService()
        old_symbols = [a.symbol for a in old_assets]
        old_prices = price_service.get_prices(old_symbols)

        total_value = 0
        for a in old_assets:
            units = float(a.units or 0)
            if units <= 0:
                # Fallback для старых портфелей без units
                asset_val = float(portfolio.initial_amount) * float(a.percentage) / 100
                price = old_prices.get(a.symbol) or float(a.initial_price or 0)
                units = (asset_val / price) if price else 0
            price = old_prices.get(a.symbol) or float(a.initial_price or 0)
            total_value += units * (price or 0)

        symbols = [asset.get('symbol', '').upper() for asset in assets_data]
        current_prices = price_service.get_prices(symbols)

        # Удаляем старые активы
        portfolio.assets.all().delete()
        
        # Создаём новые активы с units
        new_assets = []
        for asset_data in assets_data:
            symbol = asset_data.get('symbol', '').upper()
            name = asset_data.get('name', symbol)
            percentage = asset_data.get('percentage', 0)
            pct = float(percentage)

            if symbol in old_initial_prices and old_initial_prices[symbol]:
                initial_price = old_initial_prices[symbol]
            else:
                initial_price = current_prices.get(symbol, 0)

            price = current_prices.get(symbol, 0) or float(initial_price or 0)
            asset_value = total_value * pct / 100
            units = (asset_value / price) if price else 0

            asset = PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol=symbol,
                name=name,
                percentage=percentage,
                initial_price=initial_price,
                units=units
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
