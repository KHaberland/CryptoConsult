"""
Тесты CRUD для модели Wallet (PLAN06 — ЭТАП 7, T1).

Покрываем:
* создание кошелька;
* отказ при дубликате имени внутри одного портфеля;
* обновление полей (PATCH);
* удаление пустого кошелька (без holdings и с нулевыми holdings);
* запрет удаления кошелька с ненулевым балансом;
* запрет удаления default-кошелька.

Используется pytest + pytest-django (см. backend/pytest.ini, conftest.py).
"""

import uuid
from decimal import Decimal

import pytest

from portfolios.models import (
    Portfolio,
    Wallet,
    WalletHolding,
)


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
    """Активный портфель для текущей сессии."""
    return Portfolio.objects.create(
        session_id=session_id,
        name='Тестовый портфель',
        initial_amount=Decimal('5000'),
        target_years=5,
        is_active=True,
    )


@pytest.fixture
def default_wallet(portfolio):
    """Создаём default-кошелёк, как это делает backfill-миграция."""
    return Wallet.objects.create(
        portfolio=portfolio,
        name='Общий кошелёк',
        type=Wallet.TYPE_OTHER,
        is_default=True,
    )


@pytest.fixture
def url_list():
    return '/api/portfolio/wallets/'


def _detail_url(wallet_id: int) -> str:
    return f'/api/portfolio/wallets/{wallet_id}/'


# ---------------------------------------------------------------------------
# Создание
# ---------------------------------------------------------------------------


class TestWalletCreate:
    """POST /api/portfolio/wallets/ — создание."""

    def test_create_wallet_minimal(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        """Создание кошелька с минимальным набором полей."""
        response = api_client.post(
            url_list,
            {'name': 'Binance', 'type': Wallet.TYPE_EXCHANGE},
            format='json',
            **session_headers,
        )

        assert response.status_code == 201, response.content
        data = response.json()
        assert data['name'] == 'Binance'
        assert data['type'] == Wallet.TYPE_EXCHANGE
        assert data['is_default'] is False
        assert data['portfolio_id'] == portfolio.id
        assert data['holdings'] == []

        wallet = Wallet.objects.get(pk=data['id'])
        assert wallet.portfolio_id == portfolio.id
        assert wallet.note == ''

    def test_create_wallet_with_note(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        """Поле note сохраняется."""
        response = api_client.post(
            url_list,
            {
                'name': 'Ledger Nano X',
                'type': Wallet.TYPE_COLD,
                'note': 'основной cold-storage',
            },
            format='json',
            **session_headers,
        )

        assert response.status_code == 201, response.content
        wallet = Wallet.objects.get(pk=response.json()['id'])
        assert wallet.note == 'основной cold-storage'

    def test_create_wallet_blank_name_rejected(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        """Пустое имя → 400 (валидация сериализатора)."""
        response = api_client.post(
            url_list,
            {'name': '   ', 'type': Wallet.TYPE_EXCHANGE},
            format='json',
            **session_headers,
        )
        assert response.status_code == 400, response.content
        # Никакого нового кошелька не создалось (есть только default).
        assert Wallet.objects.filter(portfolio=portfolio).count() == 1

    def test_create_wallet_no_active_portfolio(
        self, api_client, db, session_headers, url_list
    ):
        """Если у сессии нет активного портфеля → 404."""
        response = api_client.post(
            url_list,
            {'name': 'Binance', 'type': Wallet.TYPE_EXCHANGE},
            format='json',
            **session_headers,
        )
        assert response.status_code == 404, response.content

    def test_create_wallet_as_new_default_demotes_previous(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        """Создание с is_default=True снимает флаг с прежнего default."""
        response = api_client.post(
            url_list,
            {
                'name': 'Холодный',
                'type': Wallet.TYPE_COLD,
                'is_default': True,
            },
            format='json',
            **session_headers,
        )

        assert response.status_code == 201, response.content
        new_wallet = Wallet.objects.get(pk=response.json()['id'])
        default_wallet.refresh_from_db()
        assert new_wallet.is_default is True
        assert default_wallet.is_default is False
        # default остаётся ровно один.
        assert Wallet.objects.filter(
            portfolio=portfolio, is_default=True
        ).count() == 1


# ---------------------------------------------------------------------------
# Уникальность имени
# ---------------------------------------------------------------------------


class TestWalletDuplicateName:
    """Дубликат имени в одном портфеле запрещён (unique_together)."""

    def test_duplicate_name_within_portfolio_rejected(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        Wallet.objects.create(
            portfolio=portfolio,
            name='Binance',
            type=Wallet.TYPE_EXCHANGE,
        )
        response = api_client.post(
            url_list,
            {'name': 'Binance', 'type': Wallet.TYPE_EXCHANGE},
            format='json',
            **session_headers,
        )
        assert response.status_code == 400, response.content
        assert Wallet.objects.filter(
            portfolio=portfolio, name='Binance'
        ).count() == 1

    def test_same_name_in_different_portfolios_allowed(
        self, api_client, db
    ):
        """Одно и то же имя в РАЗНЫХ портфелях разрешено."""
        p1 = Portfolio.objects.create(
            session_id=str(uuid.uuid4()),
            initial_amount=Decimal('1000'),
            target_years=3,
            is_active=True,
        )
        p2 = Portfolio.objects.create(
            session_id=str(uuid.uuid4()),
            initial_amount=Decimal('1000'),
            target_years=3,
            is_active=True,
        )
        Wallet.objects.create(portfolio=p1, name='Binance', type=Wallet.TYPE_EXCHANGE)
        # Тот же name в другом портфеле — БД не должна ругаться.
        Wallet.objects.create(portfolio=p2, name='Binance', type=Wallet.TYPE_EXCHANGE)
        assert Wallet.objects.filter(name='Binance').count() == 2


# ---------------------------------------------------------------------------
# Обновление
# ---------------------------------------------------------------------------


class TestWalletUpdate:
    """PATCH /api/portfolio/wallets/<pk>/ — обновление."""

    def test_update_name_and_note(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        wallet = Wallet.objects.create(
            portfolio=portfolio,
            name='Старое имя',
            type=Wallet.TYPE_HOT,
            note='старый комментарий',
        )

        response = api_client.patch(
            _detail_url(wallet.id),
            {'name': 'Новое имя', 'note': 'новый комментарий'},
            format='json',
            **session_headers,
        )

        assert response.status_code == 200, response.content
        data = response.json()
        assert data['name'] == 'Новое имя'
        assert data['note'] == 'новый комментарий'

        wallet.refresh_from_db()
        assert wallet.name == 'Новое имя'
        assert wallet.note == 'новый комментарий'
        assert wallet.type == Wallet.TYPE_HOT  # не меняли

    def test_update_type(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        wallet = Wallet.objects.create(
            portfolio=portfolio,
            name='Холодный',
            type=Wallet.TYPE_HOT,
        )
        response = api_client.patch(
            _detail_url(wallet.id),
            {'type': Wallet.TYPE_COLD},
            format='json',
            **session_headers,
        )
        assert response.status_code == 200, response.content
        wallet.refresh_from_db()
        assert wallet.type == Wallet.TYPE_COLD

    def test_update_to_duplicate_name_rejected(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        Wallet.objects.create(
            portfolio=portfolio, name='Binance', type=Wallet.TYPE_EXCHANGE
        )
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Bybit', type=Wallet.TYPE_EXCHANGE
        )

        response = api_client.patch(
            _detail_url(wallet.id),
            {'name': 'Binance'},
            format='json',
            **session_headers,
        )
        assert response.status_code == 400, response.content
        wallet.refresh_from_db()
        assert wallet.name == 'Bybit'

    def test_update_promote_to_default_demotes_previous(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Cold', type=Wallet.TYPE_COLD
        )
        response = api_client.patch(
            _detail_url(wallet.id),
            {'is_default': True},
            format='json',
            **session_headers,
        )
        assert response.status_code == 200, response.content
        wallet.refresh_from_db()
        default_wallet.refresh_from_db()
        assert wallet.is_default is True
        assert default_wallet.is_default is False

    def test_cannot_unset_default_flag(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        """Снятие флага default напрямую через PATCH запрещено."""
        response = api_client.patch(
            _detail_url(default_wallet.id),
            {'is_default': False},
            format='json',
            **session_headers,
        )
        assert response.status_code == 400, response.content
        default_wallet.refresh_from_db()
        assert default_wallet.is_default is True

    def test_update_other_session_returns_404(
        self, api_client, portfolio, default_wallet
    ):
        """Чужая сессия → не видит кошелёк → 404."""
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Binance', type=Wallet.TYPE_EXCHANGE
        )
        response = api_client.patch(
            _detail_url(wallet.id),
            {'name': 'Hacked'},
            format='json',
            HTTP_X_SESSION_ID=str(uuid.uuid4()),
        )
        assert response.status_code == 404, response.content


# ---------------------------------------------------------------------------
# Удаление
# ---------------------------------------------------------------------------


class TestWalletDelete:
    """DELETE /api/portfolio/wallets/<pk>/ — правила удаления."""

    def test_delete_empty_wallet(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        """Пустой не-default кошелёк удаляется (204)."""
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Пустой', type=Wallet.TYPE_HOT
        )
        response = api_client.delete(
            _detail_url(wallet.id),
            **session_headers,
        )
        assert response.status_code == 204, response.content
        assert not Wallet.objects.filter(pk=wallet.id).exists()

    def test_delete_wallet_with_zero_holdings(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        """Holdings есть, но units = 0 — удалять можно."""
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Zeroed', type=Wallet.TYPE_HOT
        )
        WalletHolding.objects.create(
            wallet=wallet, symbol='BTC', units=Decimal('0')
        )
        response = api_client.delete(
            _detail_url(wallet.id),
            **session_headers,
        )
        assert response.status_code == 204, response.content
        assert not Wallet.objects.filter(pk=wallet.id).exists()

    def test_delete_wallet_with_balance_forbidden(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        """Ненулевой баланс → 400, кошелёк не удалён."""
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Hot', type=Wallet.TYPE_HOT
        )
        WalletHolding.objects.create(
            wallet=wallet, symbol='BTC', units=Decimal('0.10')
        )

        response = api_client.delete(
            _detail_url(wallet.id),
            **session_headers,
        )
        assert response.status_code == 400, response.content
        assert Wallet.objects.filter(pk=wallet.id).exists()
        # holding не тронут
        assert WalletHolding.objects.filter(
            wallet=wallet, symbol='BTC'
        ).first().units == Decimal('0.10')

    def test_delete_default_wallet_forbidden(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        """default-кошелёк удалить нельзя — 400."""
        response = api_client.delete(
            _detail_url(default_wallet.id),
            **session_headers,
        )
        assert response.status_code == 400, response.content
        assert Wallet.objects.filter(pk=default_wallet.id).exists()

    def test_delete_other_session_returns_404(
        self, api_client, portfolio, default_wallet
    ):
        """Чужая сессия не может удалить кошелёк."""
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Foreign', type=Wallet.TYPE_HOT
        )
        response = api_client.delete(
            _detail_url(wallet.id),
            HTTP_X_SESSION_ID=str(uuid.uuid4()),
        )
        assert response.status_code == 404, response.content
        assert Wallet.objects.filter(pk=wallet.id).exists()


# ---------------------------------------------------------------------------
# List/Retrieve (заодно проверим, что они работают и видят holdings)
# ---------------------------------------------------------------------------


class TestWalletList:
    def test_list_returns_only_session_wallets(
        self, api_client, portfolio, default_wallet, session_headers, url_list
    ):
        Wallet.objects.create(
            portfolio=portfolio, name='Binance', type=Wallet.TYPE_EXCHANGE
        )
        # «чужой» портфель с тем же именем кошелька
        other = Portfolio.objects.create(
            session_id=str(uuid.uuid4()),
            initial_amount=Decimal('1000'),
            target_years=3,
            is_active=True,
        )
        Wallet.objects.create(
            portfolio=other, name='Foreign', type=Wallet.TYPE_HOT
        )

        response = api_client.get(url_list, **session_headers)
        assert response.status_code == 200, response.content
        names = sorted(w['name'] for w in response.json())
        assert names == ['Binance', 'Общий кошелёк']

    def test_retrieve_includes_holdings(
        self, api_client, portfolio, default_wallet, session_headers
    ):
        wallet = Wallet.objects.create(
            portfolio=portfolio, name='Hot', type=Wallet.TYPE_HOT
        )
        WalletHolding.objects.create(
            wallet=wallet, symbol='BTC', units=Decimal('0.05')
        )
        response = api_client.get(_detail_url(wallet.id), **session_headers)
        assert response.status_code == 200, response.content
        data = response.json()
        assert data['name'] == 'Hot'
        assert len(data['holdings']) == 1
        assert data['holdings'][0]['symbol'] == 'BTC'
        assert Decimal(data['holdings'][0]['units']) == Decimal('0.05')
