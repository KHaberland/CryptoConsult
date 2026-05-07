"""
Тесты подсчёта USD-стоимости кошелька (PLAN10 — A3).

Проверяют сериализаторы ``WalletHoldingSerializer.value_usd`` и
``WalletSerializer.total_value_usd`` через интеграционный путь:
GET /api/portfolio/wallets/<pk>/ с замоканным ``PriceService.get_prices``.

Фиксируем поведение из A1:
* ``value_usd`` для holding'а — ``None``, если цены нет;
* ``total_value_usd`` суммирует только известные цены, иначе ``0.0``
  (то есть «Всего» не пропадает из UI при частично известных ценах).
"""

import uuid
from decimal import Decimal

import pytest

from portfolios.models import (
    Portfolio,
    Wallet,
    WalletHolding,
)
from portfolios.services import PriceService


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def session_id():
    return str(uuid.uuid4())


@pytest.fixture
def session_headers(session_id):
    return {'HTTP_X_SESSION_ID': session_id}


@pytest.fixture
def portfolio(db, session_id):
    return Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый портфель',
        initial_amount=Decimal('5000'),
        target_years=5,
        is_active=True,
    )


@pytest.fixture
def default_wallet(portfolio):
    """Default-кошелёк (как создаёт backfill-миграция). В тестах остаётся пустым."""
    return Wallet.objects.create(
        portfolio=portfolio,
        name='Общий кошелёк',
        type=Wallet.TYPE_OTHER,
        is_default=True,
    )


@pytest.fixture
def wallet_with_holdings(portfolio, default_wallet):
    """Кошелёк ``Hot`` с тремя позициями: 0.5 BTC, 1 ETH, 10 XYZ.

    XYZ — заведомо «неизвестный» рынку символ: ``PriceService.get_prices``
    в моках для него цену не вернёт (см. ``mock_prices``), что моделирует
    случай отсутствующей котировки.
    """
    wallet = Wallet.objects.create(
        portfolio=portfolio,
        name='Hot',
        type=Wallet.TYPE_HOT,
    )
    WalletHolding.objects.create(wallet=wallet, symbol='BTC', units=Decimal('0.5'))
    WalletHolding.objects.create(wallet=wallet, symbol='ETH', units=Decimal('1'))
    WalletHolding.objects.create(wallet=wallet, symbol='XYZ', units=Decimal('10'))
    return wallet


@pytest.fixture
def mock_prices(monkeypatch):
    """Мок ``PriceService.get_prices``: BTC=100000, ETH=3500, XYZ отсутствует."""
    table = {'BTC': 100000.0, 'ETH': 3500.0}

    def fake_get_prices(self, symbols):
        return {s: table[s] for s in (symbols or []) if s in table}

    monkeypatch.setattr(PriceService, 'get_prices', fake_get_prices)


def _detail_url(wallet_id: int) -> str:
    return f'/api/portfolio/wallets/{wallet_id}/'


def _holding_by_symbol(holdings, symbol):
    for h in holdings:
        if h['symbol'] == symbol:
            return h
    raise AssertionError(f'В ответе нет holding со symbol={symbol!r}')


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestWalletValueUsd:
    """GET /api/portfolio/wallets/<pk>/ с замоканным PriceService.get_prices."""

    def test_holding_value_usd_present(
        self,
        api_client,
        wallet_with_holdings,
        session_headers,
        mock_prices,
    ):
        """Для каждой позиции с известной ценой считается ``value_usd``."""
        response = api_client.get(
            _detail_url(wallet_with_holdings.id),
            **session_headers,
        )
        assert response.status_code == 200, response.content

        holdings = response.json()['holdings']
        btc = _holding_by_symbol(holdings, 'BTC')
        eth = _holding_by_symbol(holdings, 'ETH')

        assert btc['value_usd'] == 50000.00  # 0.5 * 100000
        assert eth['value_usd'] == 3500.00   # 1 * 3500

    def test_total_value_usd_sum(
        self,
        api_client,
        wallet_with_holdings,
        session_headers,
        mock_prices,
    ):
        """``total_value_usd`` = сумма value_usd по всем позициям с ценой."""
        response = api_client.get(
            _detail_url(wallet_with_holdings.id),
            **session_headers,
        )
        assert response.status_code == 200, response.content

        data = response.json()
        # XYZ-цены нет, поэтому он в сумму не попадает: 50000 + 3500 = 53500.
        assert data['total_value_usd'] == 53500.00

    def test_value_usd_null_when_no_price(
        self,
        api_client,
        wallet_with_holdings,
        session_headers,
        mock_prices,
    ):
        """Если цены нет — ``value_usd is None``, а ``total_value_usd``
        суммирует только известные позиции (а не падает в ``None``)."""
        response = api_client.get(
            _detail_url(wallet_with_holdings.id),
            **session_headers,
        )
        assert response.status_code == 200, response.content

        data = response.json()
        xyz = _holding_by_symbol(data['holdings'], 'XYZ')

        assert xyz['value_usd'] is None
        assert data['total_value_usd'] == 53500.00
