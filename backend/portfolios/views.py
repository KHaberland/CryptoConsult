from decimal import Decimal
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from datetime import date
from django.db import transaction

from .models import (
    Portfolio,
    PortfolioAsset,
    PortfolioContribution,
    PortfolioContributionItem,
    PortfolioSwap,
    PortfolioWithdrawal,
    Wallet,
    WalletHolding,
    WalletTransfer,
    HoldingAdjustment,
)
from .serializers import (
    PortfolioSerializer,
    PortfolioCreateSerializer,
    ContributeByUnitsSerializer,
    SwapInputSerializer,
    WalletTransferInputSerializer,
    HoldingAdjustInputSerializer,
    WalletSerializer,
    WalletCreateSerializer,
    WalletUpdateSerializer,
)
from .services import PriceService, WalletLedger, recompute_percentages_by_market
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
                'units': float(asset.get('units') or 0),
                'initial_value': round(asset['initial_value'], 2),
                'current_value': round(asset['current_value'], 2),
                'current_price': asset['current_price'],
                'change_24h': round(asset['change_24h'], 2),
                'profit_loss': round(asset['profit_loss'], 2),
                'profit_loss_percent': round(asset['profit_loss_percent'], 2),
                'is_recommended': bool(asset.get('is_recommended', True)),
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
        
        # Список выводов средств (дата и сумма)
        withdrawals = [
            {
                'id': w.id,
                'amount': float(w.amount),
                'withdrawn_at': w.withdrawn_at,
            }
            for w in portfolio.withdrawals.all().order_by('withdrawn_at')
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
            'withdrawals': withdrawals,
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
    """
    Внесение взноса в портфель.

    Поддерживает два режима:
    - DCA (по сумме $): body = { "amount": <usd> }
    - По монетам:       body = { "items": [{symbol, units, purchase_price?, purchased_at?}, ...] }
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()

        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.data.get('items') is not None:
            return self._contribute_by_units(portfolio, request.data)

        return self._contribute_by_amount(portfolio, request.data)

    def _contribute_by_amount(self, portfolio, data):
        """Старый режим — пропорциональное распределение USD по существующим активам."""
        try:
            amount = float(data.get('amount', 0))
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

        contribution = PortfolioContribution.objects.create(
            portfolio=portfolio,
            amount=amount,
        )

        assets = portfolio.assets.all()
        symbols = [asset.symbol for asset in assets]
        price_service = PriceService()
        current_prices = price_service.get_prices(symbols)

        for asset in assets:
            pct = float(asset.percentage)
            asset_value = amount * pct / 100
            price = current_prices.get(asset.symbol, 0) or float(asset.initial_price or 0)
            new_units = (asset_value / price) if price else 0

            if new_units > 0:
                old_units = float(asset.units or 0)
                if old_units <= 0:
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

    def _contribute_by_units(self, portfolio, data):
        """Новый режим — пользователь сам указывает монеты, units и (опц.) цены.

        Units всегда записываются через WalletLedger:
            * если задан wallet_id — используется указанный кошелёк портфеля;
            * иначе — default-кошелёк (создастся при необходимости).
        После всех add_units вызывается sync_aggregate для каждого изменённого
        символа, поэтому PortfolioAsset.units всегда == Σ WalletHolding.units.
        """
        serializer = ContributeByUnitsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data['items']
        wallet_id = serializer.validated_data.get('wallet_id')

        price_service = PriceService()

        # До любых изменений — затвердеваем DCA-коррекцию (если активна),
        # чтобы новые units не попали под последующее масштабирование.
        PortfolioAnalyzer(portfolio).finalize_dca_scale()

        # Свежие цены: пара (символы из items) ∪ (символы существующих активов)
        item_symbols = [it['symbol'] for it in items]
        existing_symbols = [a.symbol for a in portfolio.assets.all()]
        all_symbols = list({*item_symbols, *existing_symbols})
        current_prices = price_service.get_prices(all_symbols) if all_symbols else {}

        # ТОП-10 для отметки is_recommended у новых активов
        try:
            top10_set = set(price_service.get_top10_recommended_symbols())
        except Exception:
            top10_set = set()

        with transaction.atomic():
            # Определяем рабочий кошелёк (явный или default).
            if wallet_id is not None:
                wallet = Wallet.objects.filter(
                    portfolio=portfolio, id=wallet_id
                ).first()
                if wallet is None:
                    return Response(
                        {'detail': f'Кошелёк id={wallet_id} не найден '
                                   f'в этом портфеле.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                wallet = WalletLedger.get_default_wallet(portfolio)

            # Лениво подтягиваем WalletHolding к существующим PortfolioAsset.units
            # (для портфелей, созданных до миграции 0008 backfill).
            WalletLedger.ensure_consistent_holdings(portfolio)

            total_value = 0.0
            assets_by_symbol = {a.symbol: a for a in portfolio.assets.all()}
            affected_symbols: set[str] = set()

            # Сначала создаём общий PortfolioContribution, items привяжем к нему
            contribution = PortfolioContribution.objects.create(
                portfolio=portfolio,
                amount=Decimal('0'),
            )

            contribution_items = []

            for item in items:
                symbol = item['symbol']
                add_units = float(item['units'])

                pp_raw = item.get('purchase_price')
                if pp_raw is None or pp_raw == '':
                    purchase_price = float(current_prices.get(symbol) or 0)
                else:
                    purchase_price = float(pp_raw)
                if purchase_price <= 0:
                    purchase_price = float(current_prices.get(symbol) or 0)

                if purchase_price <= 0:
                    return Response(
                        {'detail': f'Не удалось определить цену для {symbol}. '
                                   f'Укажите purchase_price вручную.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                value_usd = add_units * purchase_price
                total_value += value_usd

                asset = assets_by_symbol.get(symbol)
                if asset:
                    # old_units берём из текущего PortfolioAsset.units — он уже
                    # синхронен с Σ WalletHolding.units после
                    # ensure_consistent_holdings.
                    old_units = float(asset.units or 0)
                    old_price = float(asset.initial_price or 0)
                    new_total_units = old_units + add_units

                    if new_total_units > 0 and old_units > 0 and old_price > 0:
                        weighted_price = (
                            (old_units * old_price) + (add_units * purchase_price)
                        ) / new_total_units
                    else:
                        weighted_price = purchase_price

                    # units НЕ трогаем напрямую — пересчитаем sync_aggregate ниже.
                    asset.initial_price = Decimal(str(round(weighted_price, 8)))
                    update_fields = ['initial_price']
                    if not asset.purchased_at and item.get('purchased_at'):
                        asset.purchased_at = item.get('purchased_at')
                        update_fields.append('purchased_at')
                    asset.save(update_fields=update_fields)
                else:
                    # Новый актив: units проставит sync_aggregate из
                    # WalletHolding, поэтому изначально 0.
                    asset = PortfolioAsset.objects.create(
                        portfolio=portfolio,
                        symbol=symbol,
                        name=symbol,
                        percentage=Decimal('0'),  # пересчитается ниже по рынку
                        initial_price=Decimal(str(round(purchase_price, 8))),
                        units=Decimal('0'),
                        is_recommended=symbol in top10_set,
                        purchased_at=item.get('purchased_at') or None,
                    )
                    assets_by_symbol[symbol] = asset

                # Реальное изменение баланса — через WalletLedger.
                WalletLedger.add_units(
                    wallet, symbol, Decimal(str(add_units))
                )
                affected_symbols.add(symbol)

                contribution_items.append(PortfolioContributionItem(
                    contribution=contribution,
                    symbol=symbol,
                    units=Decimal(str(round(add_units, 8))),
                    purchase_price=Decimal(str(round(purchase_price, 8))),
                    value_usd=Decimal(str(round(value_usd, 2))),
                ))

            if contribution_items:
                PortfolioContributionItem.objects.bulk_create(contribution_items)

            # Обновляем сумму взноса и initial_amount портфеля
            contribution.amount = Decimal(str(round(total_value, 2)))
            contribution.save(update_fields=['amount'])

            new_initial_amount = float(portfolio.initial_amount or 0) + total_value
            portfolio.initial_amount = Decimal(str(round(new_initial_amount, 2)))
            portfolio.save(update_fields=['initial_amount'])

            # Синхронизация: PortfolioAsset.units = Σ WalletHolding.units.
            for sym in affected_symbols:
                WalletLedger.sync_aggregate(portfolio, sym)

            # Пересчёт долей по рынку (после sync_aggregate, чтобы рыночная
            # стоимость считалась по актуальным units).
            recompute_percentages_by_market(portfolio, current_prices)

        portfolio.refresh_from_db()
        return Response({
            'success': True,
            'message': f'Внесено {len(items)} позиций на ${total_value:,.2f}.',
            'contribution': {
                'id': contribution.id,
                'amount': float(contribution.amount),
                'contributed_at': contribution.contributed_at,
                'items': [
                    {
                        'symbol': it.symbol,
                        'units': float(it.units),
                        'purchase_price': float(it.purchase_price),
                        'value_usd': float(it.value_usd),
                    }
                    for it in contribution_items
                ],
            },
            'portfolio': PortfolioSerializer(portfolio).data,
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


def _pick_wallet_with_max_units(portfolio, symbol: str):
    """Выбрать кошелёк портфеля с максимальным WalletHolding.units для symbol.

    Возвращает Wallet или None, если ни на одном кошельке этого символа нет.
    Используется как стратегия по умолчанию для withdraw, когда пользователь
    не указал конкретный wallet_id (см. PLAN06 — Агент 13).
    """
    sym = (symbol or '').strip().upper()
    if not sym:
        return None
    holding = (
        WalletHolding.objects
        .filter(wallet__portfolio=portfolio, symbol=sym)
        .order_by('-units')
        .select_related('wallet')
        .first()
    )
    return holding.wallet if holding else None


class WithdrawPortfolioView(APIView):
    """Выполнение вывода средств из портфеля.

    Списание units всегда идёт через WalletLedger:
        * если в элементе указан ``wallet_id`` — списываем с него;
        * иначе выбираем кошелёк с максимальным балансом по этому символу
          (fallback — default-кошелёк портфеля).
    После списания вызываем ``sync_aggregate`` по затронутым символам, так что
    ``PortfolioAsset.units`` всегда == Σ WalletHolding.units.

    Net Invested (Portfolio.initial_amount + Σ contributions − Σ withdrawals)
    при выводе НЕ переопределяется: создаётся PortfolioWithdrawal с amount и
    value_after — ровно так же, как и раньше.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        """
        Вывести средства из портфеля.

        Body:
            assets: [
                { "symbol": "BTC", "units_to_sell": 0.01, "wallet_id": 3 },
                { "symbol": "ETH", "units_to_sell": 0.5 },
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

        # Стоимость портфеля до вывода (для сохранения value_after).
        analyzer = PortfolioAnalyzer(portfolio)
        value_before = analyzer.get_current_value()['current_value']
        total_withdrawn = 0.0

        try:
            with transaction.atomic():
                # Лениво подтягиваем WalletHolding к существующим
                # PortfolioAsset.units (для портфелей, созданных до миграции
                # 0008 backfill). Иначе sync_aggregate ниже мог бы обнулить
                # исторические остатки.
                WalletLedger.ensure_consistent_holdings(portfolio)

                affected_symbols: set[str] = set()

                for item in assets_data:
                    symbol = (item.get('symbol') or '').upper().strip()
                    if not symbol:
                        continue

                    try:
                        units_to_sell = Decimal(str(item.get('units_to_sell', 0)))
                    except (TypeError, ValueError, ArithmeticError):
                        continue
                    if units_to_sell <= 0:
                        continue

                    asset = assets_by_symbol.get(symbol)
                    if not asset:
                        continue

                    # 1. Определяем кошелёк, с которого списываем.
                    wallet_id = item.get('wallet_id')
                    if wallet_id is not None:
                        try:
                            wallet_id_int = int(wallet_id)
                        except (TypeError, ValueError):
                            return Response(
                                {'detail': f'wallet_id для {symbol} некорректен.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        wallet = Wallet.objects.filter(
                            portfolio=portfolio, id=wallet_id_int
                        ).first()
                        if wallet is None:
                            return Response(
                                {'detail': f'Кошелёк id={wallet_id_int} не '
                                           f'найден в этом портфеле.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        wallet = _pick_wallet_with_max_units(portfolio, symbol)
                        if wallet is None:
                            wallet = WalletLedger.get_default_wallet(portfolio)

                    # 2. Доступный баланс — на конкретном кошельке.
                    holding = WalletHolding.objects.filter(
                        wallet=wallet, symbol=symbol
                    ).first()
                    available = (
                        Decimal(str(holding.units))
                        if holding and holding.units is not None
                        else Decimal('0')
                    )
                    # Не даём уйти в минус — режем по доступному балансу.
                    if units_to_sell > available:
                        units_to_sell = available
                    if units_to_sell <= 0:
                        continue

                    # 3. Списание с WalletHolding через WalletLedger.
                    WalletLedger.add_units(wallet, symbol, -units_to_sell)
                    affected_symbols.add(symbol)

                    # 4. USD-стоимость по текущей цене (для PortfolioWithdrawal).
                    price = float(prices.get(symbol) or 0)
                    if price > 0:
                        total_withdrawn += float(units_to_sell) * price

                # 5. Синхронизация агрегата PortfolioAsset.units по затронутым
                #    символам (PortfolioAsset.units = Σ WalletHolding.units).
                for sym in affected_symbols:
                    WalletLedger.sync_aggregate(portfolio, sym)

                # 6. Net Invested — НЕ меняем: только записываем факт вывода.
                if total_withdrawn > 0:
                    value_after = value_before - total_withdrawn
                    PortfolioWithdrawal.objects.create(
                        portfolio=portfolio,
                        amount=Decimal(str(round(total_withdrawn, 2))),
                        value_after=Decimal(
                            str(max(0, round(value_after, 2)))
                        ),
                    )
        except ValueError as exc:
            # Подстраховка: WalletLedger.add_units кидает ValueError, если
            # баланс уходит в минус (например, гонка между запросами).
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'success': True,
            'message': 'Вывод средств выполнен.',
            'total_withdrawn': round(total_withdrawn, 2),
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


# ============ Views для swap и доступных активов ============

class TradableAssetsView(APIView):
    """Список монет, доступных для пополнения / обмена в активном портфеле."""
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()

        symbols = []
        if portfolio:
            symbols = [a.symbol for a in portfolio.assets.all()]

        items = PriceService().get_available_for_trade(symbols)
        return Response({
            'assets': items,
            'count': len(items),
        })


def _get_active_portfolio(request):
    return Portfolio.objects.filter(
        session_id=request.session_id,
        is_active=True
    ).first()


def _get_units_available(portfolio, asset, units_scale: float) -> float:
    """
    Доступное (отображаемое) количество units актива с учётом DCA-коррекции.

    При активной DCA-коррекции (scale < 1) отображаемые units = raw * scale.
    """
    raw_units = float(asset.units or 0)
    if raw_units <= 0:
        # Fallback для старых портфелей без units
        pct = float(asset.percentage or 0)
        init_val = float(portfolio.initial_amount or 0) * pct / 100
        init_price = float(asset.initial_price or 0)
        if init_price > 0:
            raw_units = init_val / init_price
        else:
            raw_units = 0
    if 0 < units_scale < 1:
        return raw_units * units_scale
    return raw_units


class SwapQuoteView(APIView):
    """Котировка обмена по текущему курсу (без записи в БД)."""
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        from_symbol = (request.query_params.get('from_symbol') or '').upper().strip()
        to_symbol = (request.query_params.get('to_symbol') or '').upper().strip()

        if not from_symbol or not to_symbol:
            return Response(
                {'detail': 'Укажите from_symbol и to_symbol.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if from_symbol == to_symbol:
            return Response(
                {'detail': 'Символы «Из» и «В» не могут совпадать.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        for sym in (from_symbol, to_symbol):
            if not PriceService.is_symbol_supported(sym):
                return Response(
                    {'detail': f"Символ '{sym}' не поддерживается."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            from_units = float(request.query_params.get('from_units') or 0)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'from_units некорректен.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if from_units <= 0:
            return Response(
                {'detail': 'from_units должен быть больше нуля.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from_asset = portfolio.assets.filter(symbol=from_symbol).first()
        if not from_asset:
            return Response(
                {'detail': f'Актив {from_symbol} отсутствует в портфеле.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Если задан wallet_id — баланс показываем именно по выбранному
        # кошельку (см. PLAN06 — Агент 12). Иначе — старое поведение
        # (агрегат + DCA-scale).
        wallet_id_param = request.query_params.get('wallet_id')
        wallet = None
        wallet_units_available: Decimal | None = None
        if wallet_id_param:
            try:
                wallet_id_int = int(wallet_id_param)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'wallet_id некорректен.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            wallet = Wallet.objects.filter(
                portfolio=portfolio, id=wallet_id_int
            ).first()
            if wallet is None:
                return Response(
                    {'detail': f'Кошелёк id={wallet_id_int} не найден '
                               f'в этом портфеле.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            holding = WalletHolding.objects.filter(
                wallet=wallet, symbol=from_symbol
            ).first()
            wallet_units_available = Decimal(
                str(holding.units if holding else 0)
            )
            units_available = float(wallet_units_available)
        else:
            analyzer = PortfolioAnalyzer(portfolio)
            units_scale = analyzer.get_units_scale()
            units_available = _get_units_available(portfolio, from_asset, units_scale)

        if from_units - units_available > 1e-9:
            payload = {
                'detail': (
                    f'Недостаточно {from_symbol}'
                    + (f' на кошельке «{wallet.name}»' if wallet else '')
                    + f': доступно {units_available:.8f}, '
                    f'запрошено {from_units:.8f}.'
                ),
                'units_available': round(units_available, 8),
            }
            if wallet:
                payload['wallet_id'] = wallet.id
                payload['wallet_name'] = wallet.name
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        price_service = PriceService()
        prices = price_service.get_prices([from_symbol, to_symbol])
        from_price = float(prices.get(from_symbol) or 0)
        to_price = float(prices.get(to_symbol) or 0)

        if from_price <= 0 or to_price <= 0:
            return Response(
                {'detail': 'Не удалось получить актуальные курсы.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        value_usd = from_units * from_price
        to_units_expected = value_usd / to_price

        response_data = {
            'from_symbol': from_symbol,
            'from_units': round(from_units, 8),
            'from_price': round(from_price, 8),
            'to_symbol': to_symbol,
            'to_price': round(to_price, 8),
            'to_units_expected': round(to_units_expected, 8),
            'value_usd': round(value_usd, 2),
            'units_available': round(units_available, 8),
        }
        if wallet:
            response_data['wallet_id'] = wallet.id
            response_data['wallet_name'] = wallet.name
        return Response(response_data)


class SwapExecuteView(APIView):
    """Исполнение обмена активов внутри портфеля (без cash-in/out).

    Swap всегда происходит внутри одного кошелька (см. PLAN06 — Агент 12):
        * if wallet_id указан — используем этот кошелёк портфеля;
        * иначе — default-кошелёк портфеля (создастся при необходимости).

    Списание from_symbol и зачисление to_symbol идут через WalletLedger,
    а PortfolioAsset.units всегда пересчитывается из Σ WalletHolding.units
    через ``sync_aggregate``. Проверка баланса выполняется по конкретному
    WalletHolding, а не по агрегату PortfolioAsset.units.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SwapInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        from_symbol = d['from_symbol']
        to_symbol = d['to_symbol']
        from_units = float(d['from_units'])
        to_units = float(d['to_units'])
        note = d.get('note') or ''
        wallet_id = d.get('wallet_id')

        from_asset = portfolio.assets.filter(symbol=from_symbol).first()
        if not from_asset:
            return Response(
                {'detail': f'Актив {from_symbol} отсутствует в портфеле.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Затвердеваем DCA-коррекцию ДО изменения units, чтобы дальше работать в scale = 1.0
        PortfolioAnalyzer(portfolio).finalize_dca_scale()
        from_asset.refresh_from_db()

        price_service = PriceService()
        prices = price_service.get_prices([from_symbol, to_symbol])
        from_price = float(prices.get(from_symbol) or 0)
        to_price = float(prices.get(to_symbol) or 0)

        if from_price <= 0 or to_price <= 0:
            return Response(
                {'detail': 'Не удалось получить актуальные курсы.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            top10_set = set(price_service.get_top10_recommended_symbols())
        except Exception:
            top10_set = set()

        try:
            with transaction.atomic():
                # Определяем рабочий кошелёк (явный или default).
                if wallet_id is not None:
                    wallet = Wallet.objects.filter(
                        portfolio=portfolio, id=wallet_id
                    ).first()
                    if wallet is None:
                        return Response(
                            {'detail': f'Кошелёк id={wallet_id} не найден '
                                       f'в этом портфеле.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    wallet = WalletLedger.get_default_wallet(portfolio)

                # Подтягиваем WalletHolding к существующим PortfolioAsset.units
                # (для портфелей, созданных до миграции 0008 backfill).
                WalletLedger.ensure_consistent_holdings(portfolio)

                # Проверка баланса именно на выбранном кошельке (не по агрегату).
                from_holding = WalletLedger.get_or_create_holding(
                    wallet, from_symbol
                )
                holding_units = Decimal(str(from_holding.units or 0))
                from_units_dec = Decimal(str(from_units))
                if from_units_dec - holding_units > Decimal('0.00000001'):
                    return Response({
                        'detail': (
                            f'Недостаточно {from_symbol} на кошельке '
                            f'«{wallet.name}»: доступно '
                            f'{holding_units}, запрошено {from_units_dec}.'
                        ),
                        'wallet_id': wallet.id,
                        'wallet_name': wallet.name,
                        'units_available': float(holding_units),
                    }, status=status.HTTP_400_BAD_REQUEST)

                # 1. Списание from_symbol с конкретного WalletHolding.
                WalletLedger.add_units(wallet, from_symbol, -from_units_dec)

                # 2. Зачисление to_symbol на тот же кошелёк.
                WalletLedger.add_units(
                    wallet, to_symbol, Decimal(str(to_units))
                )

                # 3. Обновление initial_price у to_asset (взвешенная цена) и
                #    создание PortfolioAsset, если его не было. units НЕ
                #    трогаем напрямую — их выставит sync_aggregate ниже.
                to_asset = portfolio.assets.filter(symbol=to_symbol).first()
                if to_asset:
                    old_to_units = float(to_asset.units or 0)
                    old_to_price = float(to_asset.initial_price or 0)
                    new_to_units = old_to_units + to_units
                    if new_to_units > 0 and old_to_units > 0 and old_to_price > 0:
                        weighted_price = (
                            (old_to_units * old_to_price)
                            + (to_units * to_price)
                        ) / new_to_units
                    else:
                        weighted_price = to_price
                    to_asset.initial_price = Decimal(
                        str(round(weighted_price, 8))
                    )
                    to_asset.save(update_fields=['initial_price'])
                else:
                    to_asset = PortfolioAsset.objects.create(
                        portfolio=portfolio,
                        symbol=to_symbol,
                        name=to_symbol,
                        percentage=Decimal('0'),
                        initial_price=Decimal(str(round(to_price, 8))),
                        units=Decimal('0'),
                        is_recommended=to_symbol in top10_set,
                    )

                # 4. Расчёт ожидаемого количества и комиссии.
                to_units_expected = (from_units * from_price) / to_price
                fee_usd = (to_units_expected - to_units) * to_price

                # 5. Запись об обмене (с привязкой к кошельку).
                swap = PortfolioSwap.objects.create(
                    portfolio=portfolio,
                    wallet=wallet,
                    from_symbol=from_symbol,
                    from_units=Decimal(str(round(from_units, 8))),
                    from_price=Decimal(str(round(from_price, 8))),
                    to_symbol=to_symbol,
                    to_units=Decimal(str(round(to_units, 8))),
                    to_price=Decimal(str(round(to_price, 8))),
                    to_units_expected=Decimal(str(round(to_units_expected, 8))),
                    fee_usd=Decimal(str(round(fee_usd, 2))),
                    note=note,
                )

                # 6. Синхронизация агрегата PortfolioAsset.units по обоим
                #    символам (PortfolioAsset.units = Σ WalletHolding.units).
                WalletLedger.sync_aggregate(portfolio, from_symbol)
                WalletLedger.sync_aggregate(portfolio, to_symbol)

                # 7. Пересчёт долей по рынку (после sync_aggregate, чтобы
                #    рыночная стоимость считалась по актуальным units).
                recompute_percentages_by_market(portfolio, prices)
        except ValueError as exc:
            # Подстраховка: WalletLedger.add_units кидает ValueError, если
            # баланс уходит в минус (например, гонка между запросами).
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        portfolio.refresh_from_db()
        return Response({
            'success': True,
            'message': (
                f'Обмен {from_units:.8f} {from_symbol} → '
                f'{to_units:.8f} {to_symbol} выполнен.'
            ),
            'swap': {
                'id': swap.id,
                'from_symbol': swap.from_symbol,
                'from_units': float(swap.from_units),
                'from_price': float(swap.from_price),
                'to_symbol': swap.to_symbol,
                'to_units': float(swap.to_units),
                'to_price': float(swap.to_price),
                'to_units_expected': float(swap.to_units_expected),
                'fee_usd': float(swap.fee_usd),
                'note': swap.note,
                'swapped_at': swap.swapped_at,
            },
            'portfolio': PortfolioSerializer(portfolio).data,
        }, status=status.HTTP_201_CREATED)


# ============ Views для кошельков ============

class WalletListCreateView(APIView):
    """Список кошельков активного портфеля и создание нового.

    GET  /api/portfolio/wallets/   — список кошельков (с holdings) для активного
                                     портфеля сессии.
    POST /api/portfolio/wallets/   — создать кошелёк в активном портфеле.

    Уникальность имени гарантируется ``unique_together = (portfolio, name)``
    на уровне модели; здесь мы проверяем заранее, чтобы вернуть аккуратные 400.
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        wallets = (
            Wallet.objects
            .filter(portfolio=portfolio)
            .prefetch_related('holdings')
        )
        symbols = sorted({h.symbol for w in wallets for h in w.holdings.all()})
        prices = PriceService().get_prices(symbols) if symbols else {}
        return Response(
            WalletSerializer(wallets, many=True, context={'prices': prices}).data
        )

    def post(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = WalletCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        name = data['name']
        wallet_type = data.get('type', Wallet.TYPE_OTHER)
        note = data.get('note', '') or ''
        is_default = bool(data.get('is_default', False))

        if Wallet.objects.filter(portfolio=portfolio, name=name).exists():
            return Response(
                {'detail': f'Кошелёк с именем «{name}» уже существует в этом портфеле.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if is_default:
                Wallet.objects.filter(
                    portfolio=portfolio, is_default=True
                ).update(is_default=False)

            wallet = Wallet.objects.create(
                portfolio=portfolio,
                name=name,
                type=wallet_type,
                note=note,
                is_default=is_default,
            )

        return Response(
            WalletSerializer(wallet, context={'prices': {}}).data,
            status=status.HTTP_201_CREATED
        )


class WalletDetailView(APIView):
    """Детали кошелька, обновление и удаление.

    GET    /api/portfolio/wallets/<pk>/
    PATCH  /api/portfolio/wallets/<pk>/
    DELETE /api/portfolio/wallets/<pk>/

    Правила удаления (см. PLAN06 — ЭТАП 7, T1):
    * нельзя удалить кошелёк-default;
    * нельзя удалить кошелёк, на котором есть ненулевой баланс по любому активу.
    """
    permission_classes = (AllowAny,)

    def _get_wallet(self, request, pk):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return None, None
        try:
            wallet = (
                Wallet.objects
                .filter(portfolio=portfolio, pk=pk)
                .prefetch_related('holdings')
                .get()
            )
        except Wallet.DoesNotExist:
            return portfolio, None
        return portfolio, wallet

    def get(self, request, pk):
        _, wallet = self._get_wallet(request, pk)
        if wallet is None:
            return Response(
                {'detail': 'Кошелёк не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        symbols = sorted({h.symbol for h in wallet.holdings.all()})
        prices = PriceService().get_prices(symbols) if symbols else {}
        return Response(WalletSerializer(wallet, context={'prices': prices}).data)

    def patch(self, request, pk):
        portfolio, wallet = self._get_wallet(request, pk)
        if wallet is None:
            return Response(
                {'detail': 'Кошелёк не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = WalletUpdateSerializer(wallet, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_name = data.get('name')
        if new_name and new_name != wallet.name:
            if Wallet.objects.filter(
                portfolio=portfolio, name=new_name
            ).exclude(pk=wallet.pk).exists():
                return Response(
                    {'detail': f'Кошелёк с именем «{new_name}» уже существует в этом портфеле.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        is_default_new = data.get('is_default')
        if is_default_new is False and wallet.is_default:
            return Response(
                {'detail': 'Нельзя снять флаг «по умолчанию» — должен оставаться один default-кошелёк.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if is_default_new is True and not wallet.is_default:
                Wallet.objects.filter(
                    portfolio=portfolio, is_default=True
                ).update(is_default=False)

            for field in ('name', 'type', 'note', 'is_default'):
                if field in data:
                    setattr(wallet, field, data[field])
            wallet.save()

        symbols = sorted({h.symbol for h in wallet.holdings.all()})
        prices = PriceService().get_prices(symbols) if symbols else {}
        return Response(WalletSerializer(wallet, context={'prices': prices}).data)

    def delete(self, request, pk):
        _, wallet = self._get_wallet(request, pk)
        if wallet is None:
            return Response(
                {'detail': 'Кошелёк не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if wallet.is_default:
            return Response(
                {'detail': 'Нельзя удалить кошелёк по умолчанию.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        non_zero = wallet.holdings.exclude(units=Decimal('0')).exists()
        if non_zero:
            return Response(
                {'detail': 'Нельзя удалить кошелёк с ненулевым балансом. '
                           'Сначала переведите активы или скорректируйте балансы в ноль.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        wallet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WalletTransferView(APIView):
    """Перевод актива между кошельками внутри одного портфеля.

    POST /api/portfolio/wallets/transfer/
    Body:
        {
            "from_wallet_id": <int>,
            "to_wallet_id": <int>,
            "symbol": "BTC",
            "from_units": "0.10000000",
            "to_units": "0.09950000",
            "note": "перевод на холодный кошелёк"   # опционально
        }

    Логика:
        1. списываем from_units с from_wallet (через WalletLedger.add_units)
        2. зачисляем to_units на to_wallet (через WalletLedger.add_units)
        3. fee_units = from_units - to_units (>= 0)
        4. fee_usd = fee_units * текущая цена символа (если цена доступна)
        5. синхронизируем агрегат PortfolioAsset.units по этому символу

    Инвариант сохраняется: списали ровно from_units, зачислили to_units,
    разница (fee_units) уходит из общего баланса портфеля.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = WalletTransferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        from_wallet_id = d['from_wallet_id']
        to_wallet_id = d['to_wallet_id']
        symbol = d['symbol']
        from_units = d['from_units']
        to_units = d['to_units']
        note = (request.data.get('note') or '').strip()[:200]

        try:
            from_wallet = Wallet.objects.get(pk=from_wallet_id, portfolio=portfolio)
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Кошелёк-источник не найден в текущем портфеле.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            to_wallet = Wallet.objects.get(pk=to_wallet_id, portfolio=portfolio)
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Кошелёк-получатель не найден в текущем портфеле.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        fee_units = from_units - to_units
        if fee_units < 0:
            return Response(
                {'detail': 'Количество к получению не может превышать количество к отправке.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        price_service = PriceService()
        try:
            prices = price_service.get_prices([symbol])
        except Exception:
            prices = {}
        price = prices.get(symbol)
        try:
            fee_usd = (Decimal(str(price)) * fee_units) if price else Decimal('0')
        except (TypeError, ValueError):
            fee_usd = Decimal('0')
        fee_usd = fee_usd.quantize(Decimal('0.01'))

        try:
            with transaction.atomic():
                WalletLedger.add_units(from_wallet, symbol, -from_units)
                WalletLedger.add_units(to_wallet, symbol, to_units)

                transfer = WalletTransfer.objects.create(
                    portfolio=portfolio,
                    from_wallet=from_wallet,
                    to_wallet=to_wallet,
                    symbol=symbol,
                    from_units=from_units,
                    to_units=to_units,
                    fee_units=fee_units,
                    fee_usd=fee_usd,
                    occurred_on=date.today(),
                    note=note,
                )

                WalletLedger.sync_aggregate(portfolio, symbol)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'success': True,
            'message': (
                f'Переведено {from_units} {symbol}: '
                f'{from_wallet.name} → {to_wallet.name} '
                f'(зачислено {to_units}, комиссия {fee_units}).'
            ),
            'transfer': {
                'id': transfer.id,
                'from_wallet_id': from_wallet.id,
                'from_wallet_name': from_wallet.name,
                'to_wallet_id': to_wallet.id,
                'to_wallet_name': to_wallet.name,
                'symbol': transfer.symbol,
                'from_units': str(transfer.from_units),
                'to_units': str(transfer.to_units),
                'fee_units': str(transfer.fee_units),
                'fee_usd': str(transfer.fee_usd),
                'occurred_on': transfer.occurred_on,
                'note': transfer.note,
            },
        }, status=status.HTTP_201_CREATED)


class HoldingAdjustView(APIView):
    """Ручная коррекция баланса WalletHolding.

    POST /api/portfolio/wallets/<wallet_id>/holdings/<symbol>/adjust/
    Body:
        {
            "units_after": "0.04950000",
            "reason": "network_fee",   # опционально
            "note": "комиссия сети BTC",  # опционально
            "occurred_on": "2025-05-01"   # опционально (по умолчанию — сегодня)
        }

    Логика:
        1. units_before = текущий WalletHolding.units (0, если holding не было)
        2. delta = units_after - units_before
        3. WalletLedger.add_units(wallet, symbol, delta) — обновляет баланс кошелька
        4. WalletLedger.sync_aggregate(portfolio, symbol) — пересчитывает PortfolioAsset.units
        5. value_delta_usd = delta * текущая_цена  (если цена доступна)
        6. создаётся запись HoldingAdjustment

    Net Invested (Portfolio.initial_amount + Σ contributions − Σ withdrawals)
    при коррекции НЕ меняется: мы не трогаем initial_amount, не создаём
    PortfolioContribution и не создаём PortfolioWithdrawal.
    """
    permission_classes = (AllowAny,)

    def post(self, request, wallet_id: int, symbol: str):
        portfolio = _get_active_portfolio(request)
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            wallet = Wallet.objects.get(pk=wallet_id, portfolio=portfolio)
        except Wallet.DoesNotExist:
            return Response(
                {'detail': 'Кошелёк не найден в текущем портфеле.'},
                status=status.HTTP_404_NOT_FOUND
            )

        sym = (symbol or '').strip().upper()
        if not sym:
            return Response(
                {'detail': 'Не указан символ актива.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not PriceService.is_symbol_supported(sym):
            return Response(
                {'detail': f"Символ '{sym}' не поддерживается."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = HoldingAdjustInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        units_after: Decimal = d['units_after']
        reason: str = d.get('reason') or HoldingAdjustment.REASON_OTHER
        note: str = (d.get('note') or '').strip()[:200]
        occurred_on = d.get('occurred_on') or date.today()

        price_service = PriceService()
        try:
            prices = price_service.get_prices([sym])
        except Exception:
            prices = {}
        price = prices.get(sym)

        try:
            with transaction.atomic():
                # Берём (и при необходимости создаём) holding, фиксируем units_before.
                # select_for_update — защита от гонок.
                holding = WalletLedger.get_or_create_holding(wallet, sym)
                holding = WalletHolding.objects.select_for_update().get(pk=holding.pk)
                units_before: Decimal = Decimal(str(holding.units or 0))

                delta: Decimal = Decimal(str(units_after)) - units_before

                if delta == 0:
                    return Response(
                        {'detail': 'Новое значение совпадает с текущим — корректировка не требуется.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # add_units сам не даст уйти балансу в минус (но min_value=0
                # на units_after уже это гарантирует).
                WalletLedger.add_units(wallet, sym, delta)

                try:
                    value_delta_usd = (Decimal(str(price)) * delta) if price else Decimal('0')
                except (TypeError, ValueError):
                    value_delta_usd = Decimal('0')
                value_delta_usd = value_delta_usd.quantize(Decimal('0.01'))

                adjustment = HoldingAdjustment.objects.create(
                    holding=holding,
                    units_before=units_before,
                    units_after=units_after,
                    delta=delta,
                    value_delta_usd=value_delta_usd,
                    reason=reason,
                    note=note,
                    occurred_on=occurred_on,
                )

                WalletLedger.sync_aggregate(portfolio, sym)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'success': True,
            'message': (
                f'Баланс {sym} на «{wallet.name}» скорректирован: '
                f'{units_before} → {units_after} (Δ {delta}).'
            ),
            'adjustment': {
                'id': adjustment.id,
                'wallet_id': wallet.id,
                'wallet_name': wallet.name,
                'symbol': sym,
                'units_before': str(adjustment.units_before),
                'units_after': str(adjustment.units_after),
                'delta': str(adjustment.delta),
                'value_delta_usd': str(adjustment.value_delta_usd),
                'reason': adjustment.reason,
                'note': adjustment.note,
                'occurred_on': adjustment.occurred_on,
            },
        }, status=status.HTTP_201_CREATED)


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


# ============ Views для импорта существующего портфеля ============

class Top10RecommendedView(APIView):
    """ТОП-10 ликвидных криптовалют для импорта портфеля."""
    permission_classes = (AllowAny,)

    def get(self, request):
        price_service = PriceService()
        assets = price_service.get_top10_recommended_assets()
        return Response({
            'top10': assets,
            'count': len(assets),
        })


class PortfolioImportView(APIView):
    """
    Импорт существующего портфеля пользователя.

    Body:
    {
        "name": "Мой портфель (импорт)",
        "target_years": 5,
        "assets": [
            {"symbol": "BTC", "units": 0.15, "purchase_price": 60000, "purchased_at": "2024-03-15"},
            {"symbol": "ETH", "value_usd": 2500},
            {"symbol": "SHIB", "units": 1000000}
        ]
    }
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        session_id = request.session_id

        if Portfolio.objects.filter(session_id=session_id, is_active=True).exists():
            return Response(
                {'detail': 'У вас уже есть активный портфель.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        name = request.data.get('name') or 'Мой портфель'
        try:
            target_years = int(request.data.get('target_years', 5))
        except (TypeError, ValueError):
            target_years = 5
        if not 1 <= target_years <= 7:
            target_years = max(1, min(7, target_years))

        assets_input = request.data.get('assets', [])
        if not assets_input:
            return Response(
                {'detail': 'Список активов не может быть пустым.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        price_service = PriceService()
        top10 = set(price_service.get_top10_recommended_symbols())

        # Фильтруем поддерживаемые символы (известные CoinGecko)
        symbols_supported = []
        unsupported_warnings = []
        for a in assets_input:
            sym = (a.get('symbol') or '').upper().strip()
            if not sym:
                continue
            if PriceService.is_symbol_supported(sym):
                if sym not in symbols_supported:
                    symbols_supported.append(sym)
            else:
                unsupported_warnings.append({
                    'symbol': sym,
                    'message': f'Символ "{sym}" не поддерживается сервисом и будет пропущен.'
                })

        if not symbols_supported:
            return Response({
                'detail': 'Ни один из указанных активов не поддерживается.',
                'warnings': unsupported_warnings,
            }, status=status.HTTP_400_BAD_REQUEST)

        prices = price_service.get_prices(symbols_supported)

        # Парсим позиции в units, считаем initial_amount и доли
        parsed = []
        non_recommended = []
        total_initial = 0.0
        total_current = 0.0

        for a in assets_input:
            sym = (a.get('symbol') or '').upper().strip()
            if not sym or not PriceService.is_symbol_supported(sym):
                continue

            current_price = float(prices.get(sym, 0) or 0)

            purchase_price_raw = a.get('purchase_price')
            try:
                purchase_price = float(purchase_price_raw) if purchase_price_raw not in (None, '') else current_price
            except (TypeError, ValueError):
                purchase_price = current_price
            if purchase_price <= 0:
                purchase_price = current_price

            units_raw = a.get('units')
            value_raw = a.get('value_usd')

            try:
                if units_raw not in (None, ''):
                    units = float(units_raw)
                elif value_raw not in (None, '') and current_price > 0:
                    units = float(value_raw) / current_price
                else:
                    continue
            except (TypeError, ValueError):
                continue

            if units <= 0:
                continue

            initial_value = units * purchase_price
            current_value = units * current_price
            total_initial += initial_value
            total_current += current_value

            is_recommended = sym in top10
            parsed.append({
                'symbol': sym,
                'name': a.get('name') or sym,
                'units': units,
                'initial_price': purchase_price,
                'current_price': current_price,
                'current_value': current_value,
                'is_recommended': is_recommended,
                'purchased_at': a.get('purchased_at') or None,
            })

            if not is_recommended:
                non_recommended.append({
                    'symbol': sym,
                    'name': a.get('name') or sym,
                    'message': (
                        f'Альткойн {sym} не входит в наш ТОП-10 ликвидных монет '
                        f'для долгосрочного инвестирования. Рекомендуем обменять '
                        f'его на одну из монет ТОП-10 согласно нашим рекомендациям.'
                    )
                })

        if not parsed:
            return Response({
                'detail': 'Не удалось рассчитать ни одной позиции (проверьте units / value_usd).',
                'warnings': unsupported_warnings,
            }, status=status.HTTP_400_BAD_REQUEST)

        # Объединяем дубликаты символов
        merged = {}
        for p in parsed:
            sym = p['symbol']
            if sym in merged:
                m = merged[sym]
                total_units = m['units'] + p['units']
                # Средневзвешенная цена покупки
                m['initial_price'] = (
                    m['initial_price'] * m['units'] + p['initial_price'] * p['units']
                ) / total_units if total_units > 0 else m['initial_price']
                m['units'] = total_units
                m['current_value'] = total_units * p['current_price']
                # purchased_at — берём более раннюю дату, если есть
                if p['purchased_at'] and (not m['purchased_at'] or p['purchased_at'] < m['purchased_at']):
                    m['purchased_at'] = p['purchased_at']
            else:
                merged[sym] = dict(p)

        parsed_list = list(merged.values())

        # Создаём Portfolio
        portfolio = Portfolio.objects.create(
            session_id=session_id,
            name=name,
            initial_amount=Decimal(str(round(total_initial, 2))),
            target_years=target_years,
            is_imported=True,
        )

        # Доли — по текущей рыночной стоимости
        for p in parsed_list:
            pct = (p['current_value'] / total_current * 100) if total_current > 0 else 0
            PortfolioAsset.objects.create(
                portfolio=portfolio,
                symbol=p['symbol'],
                name=p['name'],
                percentage=round(pct, 2),
                initial_price=Decimal(str(p['initial_price'])),
                units=Decimal(str(p['units'])),
                is_recommended=p['is_recommended'],
                purchased_at=p['purchased_at'],
            )

        return Response({
            'success': True,
            'portfolio': PortfolioSerializer(portfolio).data,
            'non_recommended': non_recommended,
            'warnings': unsupported_warnings,
            'summary': {
                'total_initial': round(total_initial, 2),
                'total_current': round(total_current, 2),
                'profit_loss': round(total_current - total_initial, 2),
                'profit_loss_percent': round(
                    (total_current - total_initial) / total_initial * 100, 2
                ) if total_initial > 0 else 0,
            }
        }, status=status.HTTP_201_CREATED)
