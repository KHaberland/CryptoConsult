# PLAN05: Учёт чистого капитала (Net Capital) и корректный PnL портфеля

## Цель

Превратить систему из **«визуализатора портфеля»** в **финансовый трекер реального
капитала**: пользователь должен корректно видеть, **сколько денег** он реально внёс
на биржу/кошелёк, **сколько вывел**, какова **текущая стоимость портфеля** и
**реальный PnL/ROI** — отдельно от целевой суммы инвестирования.

Ключевые правила:

1. Пользователь может фиксировать **депозиты** и **выводы средств** с
   произвольной (в т.ч. прошлой) датой и опциональной заметкой.
2. Сумма по дням накапливается → отображается **итоговый Net Invested**.
3. Если пользователь не помнит дат — он указывает **только итоговую сумму**
   одним числом (режим `simple`).
4. **Цель** инвестирования (`profile.investment_amount`) и **реальный
   капитал** (`net_invested`) больше не смешиваются на дашборде.
5. Существующие операции «Внести взнос (DCA)» / «Внести по монетам» / «Swap» /
   «Вывод средств» **не ломаются**, но автоматически создают записи в
   единой таблице движения капитала, чтобы Net Invested был согласован.

---

## 1. Терминология и формулы

```
💰 Net Invested  = initial_investment + Σ deposits − Σ withdrawals
📊 Portfolio Value = Σ (asset.units × current_price)
📈 PnL           = Portfolio Value − Net Invested
📈 ROI (%)       = PnL / Net Invested × 100
🎯 Goal          = profile.investment_amount  (только для прогресса по плану)
```

| Что было раньше | Что становится |
|---|---|
| `Portfolio.initial_amount` — смешанная сумма «начало + взносы» | `Portfolio.initial_investment` — только стартовая сумма (одним числом, simple-режим). При detailed — игнорируется в пользу `CapitalTransaction`. |
| `total_invested = initial_amount + Σ contributions` (в `PortfolioAnalyzer`) | `net_invested = initial_investment + Σ deposits − Σ withdrawals`. Берётся из `CapitalLedger.compute(portfolio)`. |
| «Вложено X из Y» на карточке стоимости | Три раздельных метрики: **Net invested**, **Portfolio value**, **PnL/ROI**. **Цель** — отдельный раздел. |

---

## 2. Пользовательские сценарии

### 2.1 Новый пользователь (с нуля)

```
[Анкета] → ввод суммы инвестиций (это и стартовый капитал, и одновременно цель)
        ▼
[Создание портфеля]
   • initial_investment = investment_amount
   • mode = 'simple'
   • has_transaction_history = False
   • CapitalTransaction(deposit) создаётся автоматически с датой = start_date
        ▼
[Дашборд: Net invested = $X, Portfolio value = $X, PnL = 0]
```

### 2.2 Уже имеющийся портфель (импорт)

```
[Анкета: «У вас уже есть инвестиции?»] → да
        ▼
[Импорт активов] (текущая логика PortfolioImportView)
        ▼
[Шаг «Указать вложенный капитал»]
   • Опция А (simple):  одно число — «Я вложил суммарно ~$N»
   • Опция Б (detailed): список депозитов с датами/суммами
        ▼
[Создаётся portfolio.initial_investment + CapitalTransaction(s)]
   mode ∈ {simple, detailed} в зависимости от выбора.
```

### 2.3 Добавление депозита/вывода средств

```
[Дашборд] → блок «Движение капитала»
        ▼
┌────────────────────────────────────────────┐
│ + Депозит                                  │
│ − Вывод                                    │
│ ─────                                      │
│ Дата: [25.04.2026]   Сумма: [$500]  USD ▼  │
│ Заметка: «пополнение Binance»              │
└────────────────────────────────────────────┘
        ▼
POST /api/portfolio/capital/transaction/
        ▼
[Net Invested пересчитан, дашборд обновлён]
```

> **Важно:** добавление депозита **не покупает монеты автоматически**. Это
> просто учёт денежного потока на счёт. Покупка монет — отдельная операция
> (`/portfolio/contribute/`), которая может создавать связанный депозит
> автоматически (см. п. 4.4).

### 2.4 Отображение списка движений капитала

На дашборде — таблица под текущей таблицей «Вывод средств»:

| Дата | Тип | Сумма | Заметка |
|---|---|---|---|
| 12.01.2026 | 💰 Депозит | +$1 000 | Перевод с банка |
| 03.02.2026 | 💰 Депозит | +$500 | DCA-вход |
| 14.03.2026 | 💸 Вывод | −$200 | Тестовый вывод |
| **Итого** | | **+$1 300** (Net invested) | |

Если `mode = 'simple'` — таблица свернута, показывается одна строка
«Итого вложено: $1 300» с кнопкой «Перейти в детальный режим».

---

## 3. Backend — изменения

### 3.1 Модели — `backend/portfolios/models.py`

#### Новая модель `CapitalTransaction`

Единая таблица движения капитала по портфелю (cash-in / cash-out).

```python
class CapitalTransaction(models.Model):
    """Движение реальных денег по биржевому/брокерскому счёту."""

    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    TYPE_CHOICES = [
        (DEPOSIT, 'Депозит'),
        (WITHDRAWAL, 'Вывод'),
    ]

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name='capital_transactions',
        verbose_name='Портфель',
    )
    type = models.CharField(
        max_length=12,
        choices=TYPE_CHOICES,
        verbose_name='Тип операции',
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Сумма',
        help_text='В валюте currency. Всегда положительное число.',
    )
    currency = models.CharField(
        max_length=3,
        default='USD',
        verbose_name='Валюта',
        help_text='USD или EUR',
    )
    # Курс валюты к USD на момент операции — нужно для точного учёта Net Invested
    # в USD при currency != USD. Если USD → 1.0.
    fx_to_usd = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        verbose_name='Курс к USD',
    )
    occurred_on = models.DateField(
        verbose_name='Дата операции',
        help_text='Может быть в прошлом',
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Заметка',
    )
    # Связь с источником (опционально), чтобы не создавать дубликаты
    # при автоматическом отражении контрибутиций / выводов / импорта.
    source = models.CharField(
        max_length=24,
        blank=True,
        default='manual',
        verbose_name='Источник',
        help_text='manual | initial | contribution | withdrawal | import',
    )
    source_ref_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID связанной операции',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Движение капитала'
        verbose_name_plural = 'Движения капитала'
        ordering = ['occurred_on', 'id']
        indexes = [
            models.Index(fields=['portfolio', 'occurred_on']),
            models.Index(fields=['portfolio', 'source', 'source_ref_id']),
        ]

    def __str__(self):
        sign = '+' if self.type == self.DEPOSIT else '-'
        return f'{sign}{self.amount} {self.currency} ({self.occurred_on})'

    @property
    def amount_usd(self) -> float:
        return float(self.amount) * float(self.fx_to_usd or 1)
```

#### Новые поля в `Portfolio`

```python
class Portfolio(models.Model):
    # ... существующие поля ...

    # Стартовая сумма (single-number режим). Для detailed — копится из транзакций.
    initial_investment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Стартовая сумма ($)',
        help_text='Используется в simple-режиме как итоговая сумма инвестиций.'
    )

    SIMPLE = 'simple'
    DETAILED = 'detailed'
    CAPITAL_MODE_CHOICES = [
        (SIMPLE, 'Простой (одна сумма)'),
        (DETAILED, 'Детальный (история транзакций)'),
    ]
    capital_mode = models.CharField(
        max_length=10,
        choices=CAPITAL_MODE_CHOICES,
        default=SIMPLE,
        verbose_name='Режим учёта капитала',
    )

    has_transaction_history = models.BooleanField(
        default=False,
        verbose_name='Есть история транзакций',
    )
```

> **Важно: `initial_amount` оставляем** для обратной совместимости (legacy-код,
> миграции, импорт-вьюхи). Все новые расчёты Net Invested идут через
> `CapitalLedger`. Это поле постепенно будет deprecated.

#### Модель `Portfolio` — миграция данных

Миграция `0007_capital_transaction.py` (auto):
- Создаёт таблицу `CapitalTransaction`.
- Добавляет поля `initial_investment`, `capital_mode`, `has_transaction_history`.

Затем — **дата-миграция** `0008_backfill_capital_transactions.py`:

```python
def backfill_capital_transactions(apps, schema_editor):
    Portfolio = apps.get_model('portfolios', 'Portfolio')
    CapitalTransaction = apps.get_model('portfolios', 'CapitalTransaction')
    PortfolioContribution = apps.get_model('portfolios', 'PortfolioContribution')
    PortfolioWithdrawal = apps.get_model('portfolios', 'PortfolioWithdrawal')

    for p in Portfolio.objects.all():
        # 1. initial_investment ← initial_amount
        if p.initial_amount and not p.initial_investment:
            p.initial_investment = p.initial_amount
            p.capital_mode = 'simple'
            p.has_transaction_history = False
            p.save(update_fields=[
                'initial_investment', 'capital_mode', 'has_transaction_history'
            ])

        # 2. Стартовый депозит = initial_amount на start_date
        # Не создаём, если уже есть source='initial' для этого портфеля
        already_initial = CapitalTransaction.objects.filter(
            portfolio=p, source='initial'
        ).exists()
        if p.initial_amount and not already_initial:
            CapitalTransaction.objects.create(
                portfolio=p,
                type='deposit',
                amount=p.initial_amount,
                currency='USD',
                fx_to_usd=1,
                occurred_on=p.start_date,
                note='Начальный капитал (миграция)',
                source='initial',
            )

        # 3. Каждая существующая контрибуция → депозит
        for c in PortfolioContribution.objects.filter(portfolio=p):
            exists = CapitalTransaction.objects.filter(
                portfolio=p, source='contribution', source_ref_id=c.id,
            ).exists()
            if not exists:
                CapitalTransaction.objects.create(
                    portfolio=p,
                    type='deposit',
                    amount=c.amount,
                    currency='USD',
                    fx_to_usd=1,
                    occurred_on=c.contributed_at,
                    note='Внесён взнос (миграция)',
                    source='contribution',
                    source_ref_id=c.id,
                )

        # 4. Каждый существующий вывод → withdrawal
        for w in PortfolioWithdrawal.objects.filter(portfolio=p):
            exists = CapitalTransaction.objects.filter(
                portfolio=p, source='withdrawal', source_ref_id=w.id,
            ).exists()
            if not exists:
                CapitalTransaction.objects.create(
                    portfolio=p,
                    type='withdrawal',
                    amount=w.amount,
                    currency='USD',
                    fx_to_usd=1,
                    occurred_on=w.withdrawn_at,
                    note='Вывод средств (миграция)',
                    source='withdrawal',
                    source_ref_id=w.id,
                )


class Migration(migrations.Migration):
    dependencies = [('portfolios', '0007_capital_transaction')]
    operations = [migrations.RunPython(backfill_capital_transactions, migrations.RunPython.noop)]
```

PowerShell-команды:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python manage.py makemigrations portfolios -n capital_transaction
python manage.py makemigrations portfolios -n backfill_capital_transactions --empty
# вписать в файл функцию backfill (см. выше) и migrations.RunPython
python manage.py migrate
```

### 3.2 Утилита — `CapitalLedger` (`backend/portfolios/services.py`)

Единая точка расчёта Net Invested и сводки PnL.

```python
@dataclass
class CapitalSummary:
    net_invested: float
    deposits_total: float
    withdrawals_total: float
    portfolio_value: float
    pnl: float
    pnl_percent: float


class CapitalLedger:
    """Единая логика расчёта Net Capital и PnL."""

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def compute_net_invested(self) -> Tuple[float, float, float]:
        """
        Вернуть (net_invested, deposits_total, withdrawals_total) в USD.

        Источник:
        - capital_mode == 'detailed' → из CapitalTransaction.
        - capital_mode == 'simple'  → initial_investment, плюс
            учитываются явные депозиты/выводы из CapitalTransaction
            (на случай частичных правок).
        """
        deposits_total = 0.0
        withdrawals_total = 0.0

        for tx in self.portfolio.capital_transactions.all():
            v = float(tx.amount) * float(tx.fx_to_usd or 1)
            if tx.type == CapitalTransaction.DEPOSIT:
                deposits_total += v
            else:
                withdrawals_total += v

        # Если в detailed-режиме нет вообще ни одной записи — fallback на simple
        if self.portfolio.capital_mode == Portfolio.SIMPLE:
            initial = float(self.portfolio.initial_investment or 0)
            # Если в simple уже есть source='initial' депозит, не двойим;
            # ledger уже учёл его в deposits_total.
            has_initial_tx = self.portfolio.capital_transactions.filter(
                source='initial'
            ).exists()
            if not has_initial_tx and initial > 0:
                deposits_total += initial

        net = deposits_total - withdrawals_total
        return net, deposits_total, withdrawals_total

    def compute_summary(self, portfolio_value: float) -> CapitalSummary:
        net, dep, wdr = self.compute_net_invested()
        pnl = portfolio_value - net
        pnl_pct = (pnl / net * 100) if net > 0 else 0.0
        return CapitalSummary(
            net_invested=round(net, 2),
            deposits_total=round(dep, 2),
            withdrawals_total=round(wdr, 2),
            portfolio_value=round(portfolio_value, 2),
            pnl=round(pnl, 2),
            pnl_percent=round(pnl_pct, 2),
        )
```

### 3.3 Интеграция в `PortfolioAnalyzer` — `backend/advisor/services.py`

Метод `_get_total_invested()` теперь делегирует в `CapitalLedger`:

```python
def _get_total_invested(self) -> float:
    """Net Invested = initial_investment + Σ deposits − Σ withdrawals (USD)."""
    from portfolios.services import CapitalLedger
    net, _, _ = CapitalLedger(self.portfolio).compute_net_invested()
    return net
```

`get_current_value()` — без изменений по структуре, но теперь возвращает
дополнительные поля:

```python
return {
    'initial_value': total_invested,         # = net_invested
    'net_invested': total_invested,          # явное имя
    'deposits_total': deposits_total,        # для UI
    'withdrawals_total': withdrawals_total,  # для UI
    'current_value': total_value,
    'profit_loss': profit_loss,
    'profit_loss_percent': profit_loss_percent,
    'assets': assets_info,
}
```

> **Backward-compat:** ключ `initial_value` оставляем (используется во многих
> местах фронтенда и LLM-промптах), но теперь он обозначает именно Net Invested.
> Это не ломает текущий UI, лишь делает значение более точным.

#### DCA-коррекция

Логика `_get_dca_corrected_invested()` ставится в зависимость от `capital_mode`:

- `simple` (старые портфели и новые «введу сумму одним числом»): текущая
  DCA-коррекция остаётся как есть (шкалирование units).
- `detailed`: каждая часть DCA — это **отдельный депозит**; пользователь сам
  заводит реальные пополнения. DCA-коррекция отключается:
  `units_scale = 1.0`. То есть `current_value` = Σ(units × price), без скейла.

```python
def _get_dca_corrected_invested(self) -> tuple:
    if self.portfolio.capital_mode == Portfolio.DETAILED:
        return self._get_total_invested(), 1.0
    # ... текущая логика для simple
```

### 3.4 Сериализаторы — `backend/portfolios/serializers.py`

```python
class CapitalTransactionSerializer(serializers.ModelSerializer):
    amount_usd = serializers.SerializerMethodField()

    class Meta:
        model = CapitalTransaction
        fields = (
            'id', 'type', 'amount', 'currency', 'fx_to_usd',
            'amount_usd', 'occurred_on', 'note', 'source',
            'created_at',
        )
        read_only_fields = ('id', 'amount_usd', 'source', 'created_at')

    def get_amount_usd(self, obj):
        return round(obj.amount_usd, 2)


class CapitalTransactionInputSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['deposit', 'withdrawal'])
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    currency = serializers.ChoiceField(choices=['USD', 'EUR'], default='USD')
    fx_to_usd = serializers.DecimalField(
        max_digits=12, decimal_places=6, required=False, default=Decimal('1'),
        min_value=Decimal('0.000001'),
    )
    occurred_on = serializers.DateField()
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')

    def validate_occurred_on(self, value):
        from datetime import date as _date
        if value > _date.today():
            raise serializers.ValidationError('Дата не может быть в будущем.')
        return value

    def validate(self, attrs):
        # EUR без явного fx → запрос курса
        if attrs.get('currency') == 'EUR' and (
            not attrs.get('fx_to_usd') or attrs['fx_to_usd'] == Decimal('1')
        ):
            # Берём текущий курс EUR/USD (по умолчанию 1.08, можно вынести в сервис)
            attrs['fx_to_usd'] = Decimal('1.08')
        return attrs


class CapitalSummarySerializer(serializers.Serializer):
    net_invested = serializers.FloatField()
    deposits_total = serializers.FloatField()
    withdrawals_total = serializers.FloatField()
    portfolio_value = serializers.FloatField()
    pnl = serializers.FloatField()
    pnl_percent = serializers.FloatField()
    capital_mode = serializers.CharField()
    has_transaction_history = serializers.BooleanField()
    transactions = CapitalTransactionSerializer(many=True)


class InitialInvestmentSerializer(serializers.Serializer):
    """Установка одной суммы (simple-режим)."""
    initial_investment = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01')
    )
```

И в `PortfolioSerializer` добавить `initial_investment`, `capital_mode`,
`has_transaction_history`.

### 3.5 Views — `backend/portfolios/views.py`

#### `PortfolioCapitalSummaryView` (GET)

```python
class PortfolioCapitalSummaryView(APIView):
    """GET /api/portfolio/summary/ — сводка Net Invested / Portfolio Value / PnL."""
    permission_classes = (AllowAny,)

    def get(self, request):
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id, is_active=True
        ).first()
        if not portfolio:
            return Response(
                {'detail': 'Активный портфель не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )

        analyzer = PortfolioAnalyzer(portfolio)
        v = analyzer.get_current_value()
        ledger = CapitalLedger(portfolio)
        summary = ledger.compute_summary(v['current_value'])

        txs = portfolio.capital_transactions.all().order_by('occurred_on', 'id')
        return Response({
            'net_invested': summary.net_invested,
            'deposits_total': summary.deposits_total,
            'withdrawals_total': summary.withdrawals_total,
            'portfolio_value': summary.portfolio_value,
            'pnl': summary.pnl,
            'pnl_percent': summary.pnl_percent,
            'capital_mode': portfolio.capital_mode,
            'has_transaction_history': portfolio.has_transaction_history,
            'initial_investment': float(portfolio.initial_investment or 0),
            'transactions': CapitalTransactionSerializer(txs, many=True).data,
        })
```

#### `CapitalTransactionListCreateView`

```python
class CapitalTransactionListCreateView(APIView):
    """
    GET  /api/portfolio/capital/transactions/    — список транзакций.
    POST /api/portfolio/capital/transactions/    — создать депозит/вывод.
    """
    permission_classes = (AllowAny,)

    def _get_active_portfolio(self, request):
        return Portfolio.objects.filter(
            session_id=request.session_id, is_active=True
        ).first()

    def get(self, request):
        portfolio = self._get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)
        txs = portfolio.capital_transactions.all().order_by('occurred_on', 'id')
        return Response({
            'transactions': CapitalTransactionSerializer(txs, many=True).data,
            'count': txs.count(),
        })

    def post(self, request):
        portfolio = self._get_active_portfolio(request)
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)

        s = CapitalTransactionInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        with transaction.atomic():
            tx = CapitalTransaction.objects.create(
                portfolio=portfolio,
                type=d['type'],
                amount=d['amount'],
                currency=d['currency'],
                fx_to_usd=d['fx_to_usd'],
                occurred_on=d['occurred_on'],
                note=d.get('note') or '',
                source='manual',
            )
            # Переключаем режим в detailed, как только пользователь начал
            # вести историю руками.
            if portfolio.capital_mode != Portfolio.DETAILED:
                portfolio.capital_mode = Portfolio.DETAILED
                portfolio.has_transaction_history = True
                portfolio.save(update_fields=['capital_mode', 'has_transaction_history'])

        return Response(
            CapitalTransactionSerializer(tx).data,
            status=status.HTTP_201_CREATED
        )
```

#### `CapitalTransactionDetailView` (PATCH / DELETE)

Для редактирования/удаления записи:

```python
class CapitalTransactionDetailView(APIView):
    """PATCH/DELETE /api/portfolio/capital/transactions/<id>/"""
    permission_classes = (AllowAny,)

    def _get_tx(self, request, pk):
        return CapitalTransaction.objects.filter(
            pk=pk, portfolio__session_id=request.session_id
        ).first()

    def patch(self, request, pk):
        tx = self._get_tx(request, pk)
        if not tx:
            return Response({'detail': 'Не найдено.'}, status=404)
        if tx.source not in ('manual', 'initial'):
            return Response(
                {'detail': 'Авто-записи (контрибуции/выводы) редактируются через '
                           'соответствующие операции.'},
                status=400
            )
        # Принимаем только те же поля, что и при create
        s = CapitalTransactionInputSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        for k, v in s.validated_data.items():
            setattr(tx, k, v)
        tx.save()
        return Response(CapitalTransactionSerializer(tx).data)

    def delete(self, request, pk):
        tx = self._get_tx(request, pk)
        if not tx:
            return Response({'detail': 'Не найдено.'}, status=404)
        if tx.source not in ('manual', 'initial'):
            return Response(
                {'detail': 'Авто-записи удаляются через откат соответствующих операций.'},
                status=400
            )
        tx.delete()
        return Response(status=204)
```

#### `InitialInvestmentView` (POST)

Для simple-режима — установить одну сумму (или поправить).

```python
class InitialInvestmentView(APIView):
    """POST /api/portfolio/capital/initial/ — задать стартовую сумму одним числом."""
    permission_classes = (AllowAny,)

    def post(self, request):
        portfolio = Portfolio.objects.filter(
            session_id=request.session_id, is_active=True
        ).first()
        if not portfolio:
            return Response({'detail': 'Активный портфель не найден.'}, status=404)

        s = InitialInvestmentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        amount = s.validated_data['initial_investment']

        with transaction.atomic():
            portfolio.initial_investment = amount
            portfolio.capital_mode = Portfolio.SIMPLE
            portfolio.has_transaction_history = False
            portfolio.save(update_fields=[
                'initial_investment', 'capital_mode', 'has_transaction_history'
            ])
            # Обновляем (или создаём) запись source='initial'
            initial_tx = portfolio.capital_transactions.filter(source='initial').first()
            if initial_tx:
                initial_tx.amount = amount
                initial_tx.currency = 'USD'
                initial_tx.fx_to_usd = Decimal('1')
                initial_tx.occurred_on = portfolio.start_date
                initial_tx.note = 'Стартовая сумма (simple)'
                initial_tx.save()
            else:
                CapitalTransaction.objects.create(
                    portfolio=portfolio,
                    type='deposit',
                    amount=amount,
                    currency='USD',
                    fx_to_usd=Decimal('1'),
                    occurred_on=portfolio.start_date,
                    note='Стартовая сумма (simple)',
                    source='initial',
                )

        return Response(PortfolioSerializer(portfolio).data, status=200)
```

#### Хелперы для `POST /portfolio/deposit/` и `POST /portfolio/withdraw/`

ТЗ явно требует endpoints `/portfolio/deposit/` и `/portfolio/withdraw/`. Добавим
их **как алиасы** на `CapitalTransactionListCreateView` с зашитым `type`:

```python
class CapitalDepositView(CapitalTransactionListCreateView):
    def post(self, request):
        request.data['type'] = 'deposit'
        return super().post(request)


class CapitalWithdrawView(CapitalTransactionListCreateView):
    def post(self, request):
        request.data['type'] = 'withdrawal'
        return super().post(request)
```

> **Не путать с существующим `WithdrawPortfolioView`** — тот выводит **монеты**
> (продаёт активы). `CapitalWithdrawView` — это **денежный** вывод со счёта,
> просто корректирующий Net Invested.

### 3.6 Связь капитал-транзакций с портфельными операциями

Чтобы Net Invested **автоматически** реагировал на текущие операции
(пользователь не должен дублировать ввод), доработаем существующие views:

#### `ContributePortfolioView._contribute_by_amount`

После `PortfolioContribution.objects.create(...)` добавить:

```python
CapitalTransaction.objects.create(
    portfolio=portfolio,
    type='deposit',
    amount=amount,
    currency='USD',
    fx_to_usd=Decimal('1'),
    occurred_on=date.today(),
    note='Взнос (DCA)',
    source='contribution',
    source_ref_id=contribution.id,
)
```

#### `ContributePortfolioView._contribute_by_units`

После создания `PortfolioContribution` (внутри `transaction.atomic()`) — то же,
с `amount = total_value`, `note = f'Покупка {len(items)} монет(ы)'`.

#### `WithdrawPortfolioView`

После `PortfolioWithdrawal.objects.create(...)`:

```python
CapitalTransaction.objects.create(
    portfolio=portfolio,
    type='withdrawal',
    amount=Decimal(str(round(total_withdrawn, 2))),
    currency='USD',
    fx_to_usd=Decimal('1'),
    occurred_on=date.today(),
    note='Вывод средств (продажа активов)',
    source='withdrawal',
    source_ref_id=withdrawal.id,
)
```

#### `PortfolioImportView`

После создания портфеля — создаём один initial-депозит на сумму **введённого
пользователем `initial_investment`** (а не `total_initial`, который равен
произведению units × purchase_price — это технический показатель). Если
пользователь не указал `initial_investment` — используем `total_initial` как
estimate.

```python
initial_amount = Decimal(str(request.data.get('initial_investment') or total_initial))
portfolio.initial_investment = initial_amount
portfolio.capital_mode = Portfolio.SIMPLE
portfolio.has_transaction_history = False
portfolio.save(update_fields=[
    'initial_investment', 'capital_mode', 'has_transaction_history'
])
CapitalTransaction.objects.create(
    portfolio=portfolio, type='deposit',
    amount=initial_amount, currency='USD', fx_to_usd=Decimal('1'),
    occurred_on=portfolio.start_date,
    note='Импорт портфеля (стартовый капитал)',
    source='import',
)
```

#### `PortfolioCreateSerializer.create`

После `Portfolio.objects.create(...)` записываем стартовую сумму:

```python
portfolio.initial_investment = portfolio.initial_amount
portfolio.capital_mode = Portfolio.SIMPLE
portfolio.save(update_fields=['initial_investment', 'capital_mode'])
CapitalTransaction.objects.create(
    portfolio=portfolio, type='deposit',
    amount=portfolio.initial_amount, currency='USD', fx_to_usd=Decimal('1'),
    occurred_on=portfolio.start_date,
    note='Стартовый капитал',
    source='initial',
)
```

> **Защита от двойного учёта:** при автоматическом создании `CapitalTransaction`
> мы **не** меняем `Portfolio.initial_amount`. Net Invested считается через
> `CapitalLedger`. Старая формула `initial_amount + Σ contributions` больше не
> используется — заменена на ledger.

### 3.7 URL-маршруты — `backend/portfolios/urls.py`

Добавить:

```python
path('summary/', PortfolioCapitalSummaryView.as_view(), name='portfolio_summary'),

# Капитал — детальная история
path('capital/transactions/',
     CapitalTransactionListCreateView.as_view(),
     name='capital_transactions'),
path('capital/transactions/<int:pk>/',
     CapitalTransactionDetailView.as_view(),
     name='capital_transaction_detail'),

# Алиасы по ТЗ
path('deposit/', CapitalDepositView.as_view(), name='capital_deposit'),
path('withdraw-funds/', CapitalWithdrawView.as_view(), name='capital_withdraw'),
# Внимание: 'withdraw/' уже занят WithdrawPortfolioView (продажа активов).
# Чтобы не ломать контракт, новый «вывод денег» вешаем на 'withdraw-funds/'.

# Капитал — простая (одна сумма)
path('capital/initial/', InitialInvestmentView.as_view(), name='capital_initial'),
```

### 3.8 Admin — `backend/portfolios/admin.py`

```python
@admin.register(CapitalTransaction)
class CapitalTransactionAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'type', 'amount', 'currency',
                    'occurred_on', 'source', 'note')
    list_filter = ('type', 'currency', 'source', 'occurred_on')
    search_fields = ('portfolio__name', 'note')
    date_hierarchy = 'occurred_on'
```

---

## 4. Frontend — изменения

### 4.1 API-клиент — `frontend/src/services/api.ts`

```ts
export interface CapitalTransaction {
  id: number
  type: 'deposit' | 'withdrawal'
  amount: number
  currency: 'USD' | 'EUR'
  fx_to_usd: number
  amount_usd: number
  occurred_on: string  // YYYY-MM-DD
  note: string
  source: 'manual' | 'initial' | 'contribution' | 'withdrawal' | 'import'
  created_at: string
}

export interface CapitalSummary {
  net_invested: number
  deposits_total: number
  withdrawals_total: number
  portfolio_value: number
  pnl: number
  pnl_percent: number
  capital_mode: 'simple' | 'detailed'
  has_transaction_history: boolean
  initial_investment: number
  transactions: CapitalTransaction[]
}

export const capitalApi = {
  getSummary: async (): Promise<CapitalSummary> => {
    const r = await api.get('/portfolio/summary/')
    return r.data
  },

  listTransactions: async (): Promise<{ transactions: CapitalTransaction[]; count: number }> => {
    const r = await api.get('/portfolio/capital/transactions/')
    return r.data
  },

  addTransaction: async (data: {
    type: 'deposit' | 'withdrawal'
    amount: number
    currency?: 'USD' | 'EUR'
    fx_to_usd?: number
    occurred_on: string
    note?: string
  }): Promise<CapitalTransaction> => {
    const r = await api.post('/portfolio/capital/transactions/', data)
    return r.data
  },

  updateTransaction: async (id: number, data: Partial<{
    amount: number
    currency: 'USD' | 'EUR'
    fx_to_usd: number
    occurred_on: string
    note: string
  }>): Promise<CapitalTransaction> => {
    const r = await api.patch(`/portfolio/capital/transactions/${id}/`, data)
    return r.data
  },

  deleteTransaction: async (id: number): Promise<void> => {
    await api.delete(`/portfolio/capital/transactions/${id}/`)
  },

  setInitialInvestment: async (amount: number) => {
    const r = await api.post('/portfolio/capital/initial/', {
      initial_investment: amount,
    })
    return r.data
  },
}
```

### 4.2 Стор — `frontend/src/store/portfolioStore.ts`

Добавить:

```ts
capitalSummary: CapitalSummary | null
fetchCapitalSummary: (force?: boolean) => Promise<void>
addCapitalTransaction: (data: {
  type: 'deposit' | 'withdrawal'
  amount: number
  currency?: 'USD' | 'EUR'
  occurred_on: string
  note?: string
}) => Promise<void>
updateCapitalTransaction: (id: number, data: Partial<{...}>) => Promise<void>
deleteCapitalTransaction: (id: number) => Promise<void>
setInitialInvestment: (amount: number) => Promise<void>
```

После любого `add/update/delete/setInitialInvestment` — вызывать
`fetchCapitalSummary(true)` и `fetchPortfolioValue(true)`.

### 4.3 Дашборд — `frontend/src/app/dashboard/page.tsx`

#### 4.3.1 Карточка-сводка: 3 метрики

Заменить блок «Текущая стоимость / Прибыль / Убыток» на:

```tsx
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
  <Metric
    label="Net Invested"
    value={formatCurrency(capitalSummary.net_invested)}
    sublabel={`Депозиты: ${formatCurrency(capitalSummary.deposits_total)} • Выводы: ${formatCurrency(capitalSummary.withdrawals_total)}`}
    icon={<Wallet className="w-5 h-5" />}
  />
  <Metric
    label="Portfolio Value"
    value={formatCurrency(capitalSummary.portfolio_value)}
    icon={<BarChart3 className="w-5 h-5" />}
  />
  <Metric
    label="PnL"
    value={formatCurrency(capitalSummary.pnl)}
    sublabel={`ROI ${formatPercent(capitalSummary.pnl_percent)}`}
    valueClassName={capitalSummary.pnl >= 0 ? 'text-green-600' : 'text-red-600'}
    icon={capitalSummary.pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
  />
</div>
```

Полностью **удалить** строку:

```tsx
Вложено: {formatCurrency(investedSoFar)}
{totalInvestment > 0 && ` из ${formatCurrency(totalInvestment)}`}
```

#### 4.3.2 Новая секция «🎯 Цель»

Отдельным блоком в правой колонке (или над таблицей активов):

```tsx
{profile?.investment_amount && (
  <Card>
    <CardHeader><CardTitle>Цель инвестирования</CardTitle></CardHeader>
    <CardContent>
      <p className="text-sm text-gray-600">Запланированная сумма</p>
      <p className="text-2xl font-bold">{formatCurrency(profile.investment_amount)}</p>
      <Progress
        value={Math.min(100, capitalSummary.net_invested / profile.investment_amount * 100)}
        showLabel
      />
      <p className="text-xs text-gray-500 mt-1">
        Внесено: {formatCurrency(capitalSummary.net_invested)} из {formatCurrency(profile.investment_amount)}
      </p>
    </CardContent>
  </Card>
)}
```

#### 4.3.3 Секция «Движение капитала»

Расширяем существующую секцию «Вывод средств» — превращаем в общий список
капитальных транзакций (depo + withdraw) с возможностью их добавить:

```tsx
<div className="mt-6 pt-6 border-t border-gray-200">
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <Wallet className="w-5 h-5 text-primary-600" />
      <span className="font-semibold">Движение капитала</span>
      <span className="text-xs text-gray-500">
        ({capitalSummary.capital_mode === 'simple' ? 'простой режим' : 'детальный режим'})
      </span>
    </div>
    <Button size="sm" onClick={() => setShowCapitalModal(true)}>
      <PlusCircle className="w-4 h-4 mr-1" /> Добавить
    </Button>
  </div>

  {capitalSummary.capital_mode === 'simple' && !capitalSummary.has_transaction_history ? (
    <div className="rounded-lg border border-gray-200 p-4 flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-600">Стартовая сумма</p>
        <p className="text-lg font-semibold">{formatCurrency(capitalSummary.initial_investment)}</p>
      </div>
      <Button variant="secondary" size="sm" onClick={() => setShowEditInitialModal(true)}>
        Изменить
      </Button>
    </div>
  ) : (
    <CapitalTransactionsTable
      transactions={capitalSummary.transactions}
      onEdit={(tx) => setEditingTx(tx)}
      onDelete={async (id) => { await deleteCapitalTransaction(id) }}
    />
  )}
</div>
```

### 4.4 Новый компонент `CapitalTransactionModal.tsx`

`frontend/src/components/portfolio/CapitalTransactionModal.tsx`:

Поля формы:
- `type: 'deposit' | 'withdrawal'` — переключатель кнопок «+ Депозит» / «− Вывод».
- `amount: number` — input number, > 0.
- `currency: 'USD' | 'EUR'` — селект.
- `occurred_on: string` — input type=date, по умолчанию сегодня, max=today.
- `note: string` — input text, опционально.

Сабмит → `addCapitalTransaction(...)` → закрытие модалки.

### 4.5 Новый компонент `CapitalTransactionsTable.tsx`

`frontend/src/components/portfolio/CapitalTransactionsTable.tsx`:

Таблица:

| Дата | Тип | Сумма | Заметка | Действия |
|---|---|---|---|---|
| 12.01.2026 | + Депозит | +$1 000 | … | ✏ 🗑 |
| 14.03.2026 | − Вывод | −$200 | … | ✏ 🗑 |
| **Итого Net Invested** |   | **$800** |   |   |

- Записи с `source` ∈ {contribution, withdrawal, initial, import} — **read-only**
  (помечаются «авто», иконки удалить/редактировать скрыты).
- Записи с `source = 'manual'` — редактируемые.

### 4.6 Новый компонент `InitialInvestmentModal.tsx`

Один числовой input для simple-режима. Кнопка «Перейти в детальный режим»
переключает на `CapitalTransactionModal` и при первом добавлении транзакции —
бэкенд автоматически выставит `capital_mode = 'detailed'`.

### 4.7 Онбординг — `frontend/src/app/onboarding/existing-portfolio/page.tsx`

После импорта активов добавить шаг **«Сколько вы суммарно вложили?»**:

```tsx
<RadioGroup>
  <Radio value="simple">Знаю только итоговую сумму</Radio>
    {/* input → capitalApi.setInitialInvestment(amount) */}
  <Radio value="detailed">У меня есть история депозитов</Radio>
    {/* массив строк (date, amount, currency, note) → bulk POST */}
</RadioGroup>
```

### 4.8 Анкета `questionnaire/page.tsx`

Текущий `investment_amount` остаётся **целью**. Помечаем его в UI как
«Запланированная сумма инвестиций». Стартовый капитал нового портфеля
по умолчанию = `investment_amount` (как сейчас), но фронт явно поясняет:
«Если вы планируете вкладывать постепенно — позже укажите фактические
депозиты в разделе "Движение капитала"».

### 4.9 Удалить со старого UI

В `dashboard/page.tsx`:

- ❌ Текст «Вложено X из Y» в карточке стоимости.
- ❌ Прогресс-бар, смешивающий цель и капитал.
- ❌ В таблице «Состав портфеля» подпись `На сегодня (${investedSoFar} из ${totalInvestment})`
  заменить на `На сегодня (Net invested: ${capitalSummary.net_invested})`.

### 4.10 Иконки

`lucide-react`:
- Депозит: `ArrowDownToLine` (или `Plus`).
- Вывод: `ArrowUpFromLine` (или `Minus`).
- Капитал: `Wallet`.
- ROI/PnL: `TrendingUp` / `TrendingDown`.

---

## 5. Тесты — `backend/portfolios/tests/`

### 5.1 `test_capital_transactions.py`

- `test_create_deposit_changes_summary` — POST deposit → net_invested вырос.
- `test_create_withdrawal_changes_summary` — POST withdrawal → net_invested упал.
- `test_past_date_is_accepted` — `occurred_on` в прошлом (валидно).
- `test_future_date_rejected` — `occurred_on` завтра → 400.
- `test_eur_currency_uses_fx` — currency=EUR, amount=100, fx=1.08 → amount_usd=108.
- `test_capital_mode_switches_to_detailed_on_first_manual_tx` — после первого
  manual → `capital_mode = 'detailed'`, `has_transaction_history = True`.
- `test_set_initial_investment_simple_mode` — POST capital/initial/ → создан
  source='initial' депозит, mode='simple'.
- `test_update_initial_investment_replaces_existing_initial_tx` — повторный
  POST не дублирует, а обновляет ту же запись.
- `test_auto_records_dont_double_count` — после `_contribute_by_amount`:
  ровно 1 CapitalTransaction(source='contribution', source_ref_id=contribution.id).
- `test_manual_tx_can_be_edited_and_deleted`.
- `test_auto_tx_cannot_be_edited` — PATCH/DELETE на source='contribution' → 400.

### 5.2 `test_capital_ledger.py`

- `test_net_invested_simple` — initial_investment=1000, no txs → net=1000.
- `test_net_invested_detailed` — три депозита (100/200/300) − вывод 50 → 550.
- `test_pnl_calculation` — net=1000, portfolio_value=1500 → PnL=500, ROI=50%.
- `test_pnl_negative` — net=1000, portfolio_value=800 → PnL=-200, ROI=-20%.
- `test_summary_endpoint_response_shape` — все ключи присутствуют.

### 5.3 `test_backfill_migration.py`

Прогнать миграции на тестовой БД и убедиться, что:
- Старые портфели получили `initial_investment = initial_amount`.
- Создались `CapitalTransaction(source='initial')` ровно по одному на портфель.
- Все исторические `PortfolioContribution` мапятся 1-в-1 на
  `CapitalTransaction(source='contribution', source_ref_id=...)`.
- Net Invested после миграции == прежний `initial_amount + Σ contributions`.

### 5.4 Дополнения в `test_contribute_by_units.py`, `test_swap.py`

- `test_contribute_creates_capital_deposit` — после `_contribute_by_units`
  создан CapitalTransaction(deposit) с amount = total_value, source='contribution'.
- `test_swap_does_not_create_capital_tx` — swap не должен влиять на
  Net Invested. Σ deposits/withdrawals не изменился.
- `test_withdraw_creates_capital_withdrawal_record` — после `WithdrawPortfolioView`
  создан CapitalTransaction(withdrawal).

### 5.5 Запуск

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest portfolios/tests/test_capital_transactions.py portfolios/tests/test_capital_ledger.py portfolios/tests/test_backfill_migration.py -v
pytest portfolios/tests/test_contribute_by_units.py portfolios/tests/test_swap.py -v
```

---

## 6. Порядок внедрения (поэтапно)

### Этап 1. Backend — модели и миграции

1. Дописать `CapitalTransaction` в `models.py`, добавить поля в `Portfolio`.
2. Создать и применить миграции:

   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   python manage.py makemigrations portfolios -n capital_transaction
   python manage.py makemigrations portfolios -n backfill_capital_transactions --empty
   # вписать функцию backfill_capital_transactions (см. п. 3.1)
   python manage.py migrate
   ```

3. Зарегистрировать в `admin.py`.

### Этап 2. Backend — сервис и сериализаторы

1. Добавить `CapitalSummary`, `CapitalLedger` в `services.py`.
2. Поправить `PortfolioAnalyzer._get_total_invested` и `_get_dca_corrected_invested`.
3. Добавить сериализаторы в `serializers.py`.
4. Добавить поля `initial_investment`, `capital_mode`, `has_transaction_history`
   в `PortfolioSerializer`.

### Этап 3. Backend — API

1. Реализовать вьюхи: `PortfolioCapitalSummaryView`,
   `CapitalTransactionListCreateView`, `CapitalTransactionDetailView`,
   `InitialInvestmentView`, `CapitalDepositView`, `CapitalWithdrawView`.
2. Прописать маршруты в `urls.py`.
3. Доработать `ContributePortfolioView`, `WithdrawPortfolioView`,
   `PortfolioImportView`, `PortfolioCreateSerializer.create` — авто-запись
   `CapitalTransaction`.
4. Прогнать сервер:

   ```powershell
   python manage.py runserver
   # PowerShell smoke
   $sid = '11111111-1111-4111-8111-111111111111'
   curl.exe -H "X-Session-ID: $sid" http://localhost:8000/api/portfolio/summary/
   ```

### Этап 4. Backend — тесты

1. Реализовать тесты из п. 5.
2. Прогнать:

   ```powershell
   pytest portfolios/tests/ -v
   ```

### Этап 5. Frontend — API + store

1. Дописать `capitalApi` в `services/api.ts`.
2. Дописать в `portfolioStore.ts`: `capitalSummary`, `fetchCapitalSummary`,
   `addCapitalTransaction`, `updateCapitalTransaction`,
   `deleteCapitalTransaction`, `setInitialInvestment`.

### Этап 6. Frontend — UI

1. Создать компоненты `CapitalTransactionModal.tsx`,
   `CapitalTransactionsTable.tsx`, `InitialInvestmentModal.tsx`.
2. Переписать карточку «Мой портфель» в `dashboard/page.tsx` (3 метрики).
3. Добавить блок «Цель инвестирования».
4. Заменить блок «Вывод средств» на «Движение капитала» с кнопкой «Добавить».
5. В onboarding `existing-portfolio/page.tsx` — добавить шаг про вложенный
   капитал.

### Этап 7. Smoke-тест end-to-end

```powershell
# терминал 1
cd backend
.\venv\Scripts\Activate.ps1
python manage.py runserver

# терминал 2
cd frontend
npm run dev
```

Проверочный сценарий (через UI):

1. **Существующий пользователь** (после миграции): Net Invested = старая
   `initial_amount + Σ contributions`. PnL соответствует прежнему отображению.
2. **Новый пользователь**: пройти анкету → дашборд показывает Net=10 000,
   Value=10 000, PnL=0.
3. **Депозит «задним числом»**: 01.02.2026 +$500, дата = 01.02.2026 →
   Net увеличился, в таблице правильная дата.
4. **Несколько депозитов**: добавить 3 депозита с разными датами → итог
   = сумма всех. Удалить один → итог пересчитан.
5. **Simple-режим**: задать `initial_investment = $5 000` одним числом →
   Net=5 000, таблица свернута, есть кнопка «Перейти к детальному».
6. **EUR-депозит**: 100 EUR, fx=1.08 → amount_usd=108, Net вырос на $108.
7. **Swap**: обмен USDT→BTC → Net **не** меняется (только Portfolio Value).
8. **Withdraw монет** (продажа активов через текущий `WithdrawModal`):
   создаётся CapitalTransaction(withdrawal) автоматически, Net уменьшается.
9. **Цель**: запланировано 20 000 в анкете, фактический Net=5 000 →
   прогресс-бар «25%», но **не** мешает основным метрикам.

PowerShell-скрипт `scripts/smoke_plan05.ps1` — автоматизировать пп. 1–6
через REST.

---

## 7. Совместимость и риски

| Риск / нюанс | Решение |
|---|---|
| Старые портфели потеряют согласованность Net Invested. | Дата-миграция `0008_backfill_capital_transactions.py` создаёт записи `source='initial'` и `source='contribution'`/`'withdrawal'` 1-в-1 по существующим. До и после миграции `Net Invested` совпадает. |
| Двойной учёт Net Invested при contribute (контрибуция + автозапись CapitalTransaction). | `CapitalLedger` берёт ТОЛЬКО `CapitalTransaction`. `PortfolioContribution.amount` больше **не** входит в формулу — это лишь «акт покупки», а не cash-flow. |
| Существующая DCA-коррекция искажает Net. | В `simple`-режиме оставлена как есть (отображение «вложенной части»). В `detailed`-режиме отключена — пользователь сам ведёт реальные депозиты. |
| Конфликт URL: `/portfolio/withdraw/` уже занят выводом монет. | Новый «вывод денег» вешаем на `/portfolio/withdraw-funds/`. В коде frontend используем `capitalApi.addTransaction({type: 'withdrawal'})` через `/portfolio/capital/transactions/`, чтобы не плодить алиасы. ТЗ-алиасы `/portfolio/deposit/` и `/portfolio/withdraw-funds/` оставляем для совместимости. |
| LLM-промпты используют `initial_value` из `get_current_value()`. | Значение теперь = Net Invested (более точное), формат тот же → промпты не ломаются. |
| EUR-депозиты: курс зашит фиксированно (1.08). | На MVP достаточно. Дальше — подключить `PriceService.get_fx_rate('EUR', 'USD')` через CoinGecko/exchangerate.host. |
| Импортированные портфели без явной суммы инвестирования. | `PortfolioImportView` принимает опциональный `initial_investment`. Если не передан — используется `total_initial = Σ units × purchase_price`. На UI спрашиваем явно. |
| Удаление авто-CapitalTransaction приведёт к рассинхрону с `PortfolioContribution`. | В `CapitalTransactionDetailView.delete` запрещено удалять записи с `source != 'manual'` (вернётся 400). Удалять «вывод средств» можно только через откат соответствующей операции. |
| Пользователь правит `initial_investment` после того, как уже создал детальные транзакции. | `InitialInvestmentView` всегда переводит режим в `simple` и удаляет/обновляет только запись `source='initial'`. Перед сохранением — предупреждение в UI: «детальные транзакции сохранятся, но Net будет считаться как simple + ручные правки». |
| `Portfolio.initial_amount` остаётся в БД как legacy. | Не трогаем, чтобы не ломать старые места. После всех правок остаётся ссылкой на «как был создан портфель технически» (нужно для DCA-shed). Документировать как deprecated. |
| Frontend получает `portfolioValue.initial_value` со старым именем, но новым смыслом. | Это уже Net Invested (см. п. 3.3). Старый дашборд продолжит работать без правок, новый — использует `capitalSummary` для отдельных карточек. |

---

## 8. Критерии готовности

- [ ] Пользователь видит на дашборде три раздельные метрики: **Net Invested**,
      **Portfolio Value**, **PnL/ROI**. Цель — отдельным блоком.
- [ ] Пользователь может добавить депозит с произвольной (в т.ч. прошлой)
      датой. Сумма попадает в Net Invested.
- [ ] Пользователь может добавить вывод средств с произвольной датой.
      Net Invested уменьшается.
- [ ] В simple-режиме — одно числовое поле «итоговая сумма».
- [ ] В detailed-режиме — таблица с возможностью добавить/редактировать/
      удалить запись (только manual-записи).
- [ ] Swap-операции не влияют на Net Invested.
- [ ] Импорт портфеля просит сумму вложенного капитала отдельно.
- [ ] PnL = `Portfolio Value − Net Invested` точен на всех сценариях.
- [ ] Старые пользователи после миграции видят правильные числа без правок.
- [ ] Все тесты из п. 5 проходят.

---

## 9. Опционально (вне scope)

- Реальный курс валют (EUR/USD, RUB/USD) через внешний API.
- Снимки портфеля `PortfolioSnapshot` по дням — для истории Portfolio Value.
- График `Net Invested` vs `Portfolio Value` во времени.
- Поддержка нескольких портфелей у одного пользователя с раздельными ledger.
- Налоговый отчёт: лента всех realised PnL по swap/withdraw.
- Импорт CSV истории депозитов с биржи (Binance, Bybit, Kraken).
- Экспорт списка транзакций в CSV.
