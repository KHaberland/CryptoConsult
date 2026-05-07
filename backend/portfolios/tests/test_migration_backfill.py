"""
Тест data migration backfill default wallet (PLAN06 — ЭТАП 7, T5).

Покрываем сценарий:

* был Portfolio с PortfolioAsset, но без Wallet/WalletHolding
  (как до выкатки PLAN06);
* после применения ``portfolios.0008_backfill_default_wallet`` для
  каждого портфеля появляется default-кошелёк ("Общий кошелёк",
  is_default=True, type="other");
* для каждого PortfolioAsset создан WalletHolding в этом
  default-кошельке с тем же symbol и units;
* выполняется инвариант: PortfolioAsset.units == Σ WalletHolding.units
  по всем кошелькам портфеля.

Также проверяем:

* идемпотентность — повторный прогон не плодит дубликаты;
* существующий кошелёк с именем "Общий кошелёк", не помеченный
  is_default, корректно «промотируется» в default;
* портфель с уже существующим default-кошельком не получает второго;
* reverse-миграция аккуратно удаляет default-кошельки и их holdings.

Реализация:
    функция data migration принимает «исторический» apps-registry,
    но успешно работает и с реальной registry — поля совпадают.
    Поэтому вызываем ``backfill_default_wallets(django.apps.apps, None)``
    напрямую, имитируя миграцию.
"""

import importlib
import uuid
from decimal import Decimal

import pytest
from django.apps import apps as django_apps

from portfolios.models import (
    Portfolio,
    PortfolioAsset,
    Wallet,
    WalletHolding,
)


MIGRATION_MODULE = (
    'portfolios.migrations.0008_backfill_default_wallet'
)


@pytest.fixture
def migration():
    """Импортируем data migration по имени модуля."""
    return importlib.import_module(MIGRATION_MODULE)


@pytest.fixture
def session_id():
    return str(uuid.uuid4())


def _make_portfolio(session_id, name='Тестовый портфель'):
    return Portfolio.objects.create(
        session_id=session_id,
        name=name,
        initial_amount=Decimal('5000'),
        target_years=5,
        is_active=True,
    )


def _make_asset(portfolio, symbol, percentage, units, price):
    return PortfolioAsset.objects.create(
        portfolio=portfolio,
        symbol=symbol,
        name=symbol,
        percentage=Decimal(str(percentage)),
        initial_price=Decimal(str(price)),
        units=Decimal(str(units)),
        is_recommended=True,
    )


def _aggregate_units(portfolio, symbol):
    """Σ WalletHolding.units по всем кошелькам портфеля для symbol."""
    total = Decimal('0')
    for h in WalletHolding.objects.filter(
        wallet__portfolio=portfolio, symbol=symbol
    ):
        total += Decimal(h.units)
    return total


def _assert_invariant(portfolio):
    """PortfolioAsset.units == Σ WalletHolding.units для каждого актива."""
    portfolio.refresh_from_db()
    for asset in portfolio.assets.all():
        asset.refresh_from_db()
        aggregate = _aggregate_units(portfolio, asset.symbol)
        assert Decimal(asset.units) == aggregate, (
            f'инвариант нарушен для {asset.symbol}: '
            f'PortfolioAsset.units={asset.units}, '
            f'Σ WalletHolding.units={aggregate}'
        )


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBackfillDefaultWalletMigration:
    """portfolios.0008_backfill_default_wallet."""

    def test_creates_default_wallet_and_holdings_for_legacy_portfolio(
        self, migration, session_id,
    ):
        """Базовый кейс: был портфель без кошельков → появился default + holdings."""
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 80, '0.05', '100000')
        _make_asset(portfolio, 'USDT', 20, '1000', '1')

        # Точно состояние «до миграции» — никаких кошельков нет.
        assert not Wallet.objects.filter(portfolio=portfolio).exists()
        assert not WalletHolding.objects.filter(
            wallet__portfolio=portfolio
        ).exists()

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        wallets = list(Wallet.objects.filter(portfolio=portfolio))
        assert len(wallets) == 1
        default = wallets[0]
        assert default.is_default is True
        assert default.name == migration.DEFAULT_WALLET_NAME
        assert default.type == migration.DEFAULT_WALLET_TYPE

        holdings = {
            h.symbol: Decimal(h.units)
            for h in WalletHolding.objects.filter(wallet=default)
        }
        assert holdings == {
            'BTC': Decimal('0.05'),
            'USDT': Decimal('1000'),
        }

        _assert_invariant(portfolio)

    def test_invariant_holds_for_multiple_portfolios(
        self, migration, session_id,
    ):
        """Несколько портфелей одновременно — у каждого свой default."""
        p1 = _make_portfolio(session_id, name='Первый')
        _make_asset(p1, 'BTC', 100, '0.1', '100000')

        p2 = _make_portfolio(str(uuid.uuid4()), name='Второй')
        _make_asset(p2, 'ETH', 60, '2', '3500')
        _make_asset(p2, 'USDC', 40, '500', '1')

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        for portfolio in (p1, p2):
            assert (
                Wallet.objects.filter(
                    portfolio=portfolio, is_default=True
                ).count()
                == 1
            ), f'у портфеля {portfolio.name} должен быть ровно один default'
            _assert_invariant(portfolio)

    def test_is_idempotent(self, migration, session_id):
        """Повторный прогон не создаёт дубликатов и не меняет units."""
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 100, '0.05', '100000')

        migration.backfill_default_wallets(django_apps, schema_editor=None)
        migration.backfill_default_wallets(django_apps, schema_editor=None)

        assert Wallet.objects.filter(portfolio=portfolio).count() == 1
        assert (
            WalletHolding.objects.filter(
                wallet__portfolio=portfolio, symbol='BTC'
            ).count()
            == 1
        )
        _assert_invariant(portfolio)

    def test_does_not_overwrite_existing_holding_units(
        self, migration, session_id,
    ):
        """Если WalletHolding уже существует — units не затираются."""
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 100, '0.05', '100000')

        # Имитируем, что миграция уже была применена ранее, но потом
        # пользователь вручную скорректировал баланс на default-кошельке.
        wallet = Wallet.objects.create(
            portfolio=portfolio,
            name=migration.DEFAULT_WALLET_NAME,
            type=migration.DEFAULT_WALLET_TYPE,
            is_default=True,
        )
        WalletHolding.objects.create(
            wallet=wallet, symbol='BTC', units=Decimal('0.07'),
        )

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        holding = WalletHolding.objects.get(wallet=wallet, symbol='BTC')
        assert holding.units == Decimal('0.07'), (
            'миграция не должна перезаписывать units существующего holding'
        )

    def test_promotes_named_wallet_to_default(self, migration, session_id):
        """
        Кошелёк с именем «Общий кошелёк», но без is_default=True,
        должен быть промотирован в default (а не создан заново).
        """
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 100, '0.02', '100000')

        existing = Wallet.objects.create(
            portfolio=portfolio,
            name=migration.DEFAULT_WALLET_NAME,
            type=migration.DEFAULT_WALLET_TYPE,
            is_default=False,
        )

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        existing.refresh_from_db()
        assert existing.is_default is True
        # Второго кошелька с тем же именем не появилось.
        assert (
            Wallet.objects.filter(portfolio=portfolio).count() == 1
        )
        # Holding для BTC в этом кошельке создан корректно.
        holding = WalletHolding.objects.get(wallet=existing, symbol='BTC')
        assert holding.units == Decimal('0.02')
        _assert_invariant(portfolio)

    def test_preserves_existing_default_wallet(self, migration, session_id):
        """Если default-кошелёк уже есть (с другим именем) — новый не создаётся."""
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 100, '0.03', '100000')

        existing_default = Wallet.objects.create(
            portfolio=portfolio,
            name='Мой основной',
            type=Wallet.TYPE_EXCHANGE,
            is_default=True,
        )

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        wallets = list(Wallet.objects.filter(portfolio=portfolio))
        assert len(wallets) == 1
        assert wallets[0].pk == existing_default.pk
        # Holding ушёл именно в существующий default.
        holding = WalletHolding.objects.get(
            wallet=existing_default, symbol='BTC',
        )
        assert holding.units == Decimal('0.03')
        _assert_invariant(portfolio)

    def test_reverse_removes_default_wallets_and_holdings(
        self, migration, session_id,
    ):
        """reverse_backfill очищает default-кошельки с дефолтным именем."""
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 100, '0.05', '100000')

        migration.backfill_default_wallets(django_apps, schema_editor=None)
        assert WalletHolding.objects.filter(
            wallet__portfolio=portfolio
        ).exists()

        migration.reverse_backfill(django_apps, schema_editor=None)

        assert not Wallet.objects.filter(
            portfolio=portfolio,
            is_default=True,
            name=migration.DEFAULT_WALLET_NAME,
        ).exists()
        assert not WalletHolding.objects.filter(
            wallet__portfolio=portfolio
        ).exists()

    def test_skips_assets_with_blank_symbol(self, migration, session_id):
        """
        Активы с пустым symbol игнорируются (защита от мусорных строк
        в legacy-данных).
        """
        portfolio = _make_portfolio(session_id)
        _make_asset(portfolio, 'BTC', 50, '0.04', '100000')
        # Прямой UPDATE в обход .save(): эмулируем «битую» legacy-строку.
        broken = _make_asset(portfolio, 'ETH', 50, '1', '3500')
        PortfolioAsset.objects.filter(pk=broken.pk).update(symbol='   ')

        migration.backfill_default_wallets(django_apps, schema_editor=None)

        symbols = set(
            WalletHolding.objects.filter(
                wallet__portfolio=portfolio
            ).values_list('symbol', flat=True)
        )
        assert symbols == {'BTC'}
