"""Тесты MirrorPairGuard (PLAN12): запрет зеркальной пары
PortfolioContribution ↔ HoldingAdjustment в окне ±3 дня.

Сценарий, давший фантомную просадку у портфеля #27:
1) пользователь создал контрибьюшн на 0.028 BTC ≈ $2 271.89;
2) в тот же день обнулил эти 0.028 BTC корректировкой (HoldingAdjustment
   с value_delta_usd = −$2 271.89);
3) `Σ contributions` остался с этими $2 271.89, а units списались
   — старая формула P&L начала показывать −37 %.

Этот guard блокирует такие сочетания обеими сторонами:
- при попытке создать HoldingAdjustment с отрицательным value_delta_usd,
  для которого в окне ±3 дня уже есть зеркальный PortfolioContribution → 409;
- при попытке создать PortfolioContribution(item) на ту же сумму,
  для которой в окне ±3 дня уже есть отрицательный HoldingAdjustment → 409.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from portfolios.models import (
    HoldingAdjustment,
    Portfolio,
    PortfolioAsset,
    PortfolioContribution,
    PortfolioContributionItem,
    Wallet,
    WalletHolding,
)


MOCK_PRICES = {
    'BTC': 80000.0,
    'ETH': 2000.0,
    'USDT': 1.0,
}

MOCK_TOP10 = ['BTC', 'ETH']


def _setup_price_service_mock(mock_class):
    mock_service = MagicMock()
    mock_service.get_prices.return_value = MOCK_PRICES
    mock_service.get_top10_recommended_symbols.return_value = MOCK_TOP10
    mock_service.get_top10_recommended_assets.return_value = [
        {'symbol': s, 'name': s, 'current_price': MOCK_PRICES.get(s, 0), 'market_cap': 0}
        for s in MOCK_TOP10
    ]
    mock_class.return_value = mock_service
    return mock_service


def _create_portfolio_with_btc(session_id, btc_units=Decimal('0.05')):
    """Портфель с одним кошельком и BTC-позицией."""
    portfolio = Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый',
        initial_amount=Decimal('5000'),
        target_years=5,
        is_active=True,
    )
    PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol='BTC',
        name='Bitcoin',
        percentage=Decimal('100'),
        initial_price=Decimal('80000'),
        units=btc_units,
        is_recommended=True,
    )
    wallet = Wallet.objects.create(
        portfolio=portfolio,
        name='Общий кошелёк',
        type=Wallet.TYPE_OTHER,
        is_default=True,
    )
    WalletHolding.objects.create(
        wallet=wallet,
        symbol='BTC',
        units=btc_units,
    )
    return portfolio, wallet


def _create_contribution(portfolio, symbol, units, price, contributed_at=None):
    """Создать PortfolioContribution + Item на заданную позицию.

    contributed_at управляется напрямую (auto_now_add обходим через update()).
    """
    units_dec = Decimal(str(units))
    price_dec = Decimal(str(price))
    value_dec = (units_dec * price_dec).quantize(Decimal('0.01'))
    contrib = PortfolioContribution.objects.create(
        portfolio=portfolio,
        amount=value_dec,
    )
    if contributed_at is not None:
        PortfolioContribution.objects.filter(pk=contrib.pk).update(
            contributed_at=contributed_at
        )
        contrib.refresh_from_db()
    PortfolioContributionItem.objects.create(
        contribution=contrib,
        symbol=symbol,
        units=units_dec,
        purchase_price=price_dec,
        value_usd=value_dec,
    )
    return contrib


class AdjustmentBlockedByContributionTests(TestCase):
    """Adjustment с delta<0 блокируется зеркальным контрибьюшном."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _adj_url(self, wallet_id, symbol):
        return f'/api/portfolio/wallets/{wallet_id}/holdings/{symbol}/adjust/'

    @patch('portfolios.views.PriceService')
    def test_blocked_same_day(self, mock_class):
        """Контрибьюшн и adjustment в один день на ту же сумму → 409."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        # Контрибьюшн BTC 0.02 @ $80000 = $1 600 (та же дата, что и adjustment)
        _create_contribution(
            portfolio, 'BTC', Decimal('0.02'), Decimal('80000'),
            contributed_at=date.today(),
        )

        # Пытаемся списать 0.02 BTC: 0.05 → 0.03 → delta=-0.02 → value_delta=-$1600.
        response = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        payload = response.json()
        self.assertEqual(payload['error'], 'mirror_pair_conflict')
        self.assertEqual(payload['conflicting']['kind'], 'contribution')
        self.assertEqual(payload['conflicting']['symbol'], 'BTC')
        # Никаких записей создано не было.
        self.assertEqual(HoldingAdjustment.objects.count(), 0)
        # Holding/asset не тронуты.
        h = WalletHolding.objects.get(wallet=wallet, symbol='BTC')
        self.assertEqual(h.units, Decimal('0.05'))

    @patch('portfolios.views.PriceService')
    def test_blocked_within_window(self, mock_class):
        """Контрибьюшн на 2 дня раньше — в окне ±3, всё равно блок."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        _create_contribution(
            portfolio, 'BTC', Decimal('0.02'), Decimal('80000'),
            contributed_at=date.today() - timedelta(days=2),
        )

        response = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)

    @patch('portfolios.views.PriceService')
    def test_allowed_outside_window(self, mock_class):
        """Контрибьюшн на 5 дней раньше — вне окна ±3, корректировка проходит."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        _create_contribution(
            portfolio, 'BTC', Decimal('0.02'), Decimal('80000'),
            contributed_at=date.today() - timedelta(days=5),
        )

        response = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(HoldingAdjustment.objects.count(), 1)

    @patch('portfolios.views.PriceService')
    def test_allowed_for_different_symbol(self, mock_class):
        """Контрибьюшн по другой монете не блокирует корректировку BTC."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        # Контрибьюшн на ETH той же стоимости — не должен блокировать BTC-adjustment.
        _create_contribution(
            portfolio, 'ETH', Decimal('0.8'), Decimal('2000'),
            contributed_at=date.today(),
        )

        response = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

    @patch('portfolios.views.PriceService')
    def test_allowed_when_increasing_balance(self, mock_class):
        """Adjustment с delta>0 не блокируется (мы не списываем, а добавляем)."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        _create_contribution(
            portfolio, 'BTC', Decimal('0.02'), Decimal('80000'),
            contributed_at=date.today(),
        )

        # 0.05 → 0.07 → delta=+0.02 → не зеркало контрибьюшна.
        response = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.07'},
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

    @patch('portfolios.views.PriceService')
    def test_allowed_after_deleting_contribution(self, mock_class):
        """После удаления зеркального контрибьюшна — adjustment проходит."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        contrib = _create_contribution(
            portfolio, 'BTC', Decimal('0.02'), Decimal('80000'),
            contributed_at=date.today(),
        )

        # Первая попытка — 409.
        r1 = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )
        self.assertEqual(r1.status_code, status.HTTP_409_CONFLICT)

        # Удалили контрибьюшн.
        contrib.delete()

        # Повторная попытка — теперь 201.
        r2 = self.client.post(
            self._adj_url(wallet.id, 'BTC'),
            {'units_after': '0.03'},
            format='json',
            **self._headers(),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.content)


class ContributionBlockedByAdjustmentTests(TestCase):
    """Контрибьюшн блокируется зеркальным отрицательным HoldingAdjustment."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.url = '/api/portfolio/contribute/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _create_negative_adjustment(self, wallet, symbol, units, price, occurred_on=None):
        """Создаёт HoldingAdjustment с отрицательной дельтой ровно на units."""
        if occurred_on is None:
            occurred_on = date.today()
        units_dec = Decimal(str(units))
        price_dec = Decimal(str(price))
        value_dec = (-units_dec * price_dec).quantize(Decimal('0.01'))
        holding, _ = WalletHolding.objects.get_or_create(
            wallet=wallet, symbol=symbol,
            defaults={'units': Decimal('0')},
        )
        return HoldingAdjustment.objects.create(
            holding=holding,
            units_before=Decimal('0'),  # значения «снимка» для теста не важны
            units_after=Decimal('0'),
            delta=-units_dec,
            value_delta_usd=value_dec,
            reason=HoldingAdjustment.REASON_OTHER,
            occurred_on=occurred_on,
        )

    @patch('portfolios.views.PriceService')
    def test_blocked_same_day(self, mock_class):
        """Adjustment −$1 600 BTC сегодня → контрибьюшн на 0.02 BTC сегодня → 409."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        self._create_negative_adjustment(
            wallet, 'BTC', Decimal('0.02'), Decimal('80000'),
            occurred_on=date.today(),
        )

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.02, 'purchase_price': 80000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.content)
        payload = response.json()
        self.assertEqual(payload['error'], 'mirror_pair_conflict')
        self.assertEqual(payload['conflicting']['kind'], 'adjustment')
        self.assertEqual(payload['conflicting']['symbol'], 'BTC')
        # Контрибьюшн не был создан.
        self.assertEqual(PortfolioContribution.objects.count(), 0)
        self.assertEqual(PortfolioContributionItem.objects.count(), 0)

    @patch('portfolios.views.PriceService')
    def test_allowed_outside_window(self, mock_class):
        """Adjustment 5 дней назад — окно ±3 не покрывает, контрибьюшн проходит."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        self._create_negative_adjustment(
            wallet, 'BTC', Decimal('0.02'), Decimal('80000'),
            occurred_on=date.today() - timedelta(days=5),
        )

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.02, 'purchase_price': 80000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        self.assertEqual(PortfolioContribution.objects.count(), 1)

    @patch('portfolios.views.PriceService')
    def test_allowed_for_different_symbol(self, mock_class):
        """Adjustment по ETH не блокирует контрибьюшн по BTC."""
        _setup_price_service_mock(mock_class)
        portfolio, wallet = _create_portfolio_with_btc(self.session_id)
        # Чтобы adjustment мог существовать для ETH — заведём holding.
        self._create_negative_adjustment(
            wallet, 'ETH', Decimal('0.8'), Decimal('2000'),
            occurred_on=date.today(),
        )

        response = self.client.post(
            self.url,
            {
                'items': [
                    {'symbol': 'BTC', 'units': 0.02, 'purchase_price': 80000},
                ],
            },
            format='json',
            **self._headers(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
