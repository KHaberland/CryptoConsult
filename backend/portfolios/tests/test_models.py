"""
Тесты моделей портфеля.
"""

from decimal import Decimal
from django.test import TestCase

from portfolios.models import Portfolio, PortfolioAsset
from users.models import InvestorProfile


class PortfolioModelTests(TestCase):
    """Тесты модели Portfolio."""

    def setUp(self):
        self.session_id = 'test-session-123'
        InvestorProfile.objects.create(
            session_id=self.session_id,
            name='Тестовый',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
        )

    def test_portfolio_creation(self):
        """Создание портфеля с обязательными полями."""
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Мой портфель',
            initial_amount=Decimal('5000.00'),
            target_years=3,
        )
        self.assertEqual(portfolio.name, 'Мой портфель')
        self.assertEqual(portfolio.initial_amount, Decimal('5000.00'))
        self.assertEqual(portfolio.target_years, 3)
        self.assertTrue(portfolio.is_active)

    def test_portfolio_target_date(self):
        """Свойство target_date вычисляется корректно."""
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Тест',
            initial_amount=Decimal('1000'),
            target_years=2,
        )
        target = portfolio.target_date
        self.assertEqual((target - portfolio.start_date).days, 730)

    def test_portfolio_str_without_user(self):
        """__str__ для портфеля без пользователя."""
        portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Портфель',
            initial_amount=Decimal('1000'),
            target_years=1,
        )
        s = str(portfolio)
        self.assertIn('Портфель', s)
        self.assertIn(self.session_id[:8], s)


class PortfolioAssetModelTests(TestCase):
    """Тесты модели PortfolioAsset."""

    def setUp(self):
        self.session_id = 'test-session-asset'
        InvestorProfile.objects.create(
            session_id=self.session_id,
            name='Тест',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
        )
        self.portfolio = Portfolio.objects.create(
            session_id=self.session_id,
            name='Портфель',
            initial_amount=Decimal('1000'),
            target_years=3,
        )

    def test_asset_creation(self):
        """Создание актива в портфеле."""
        asset = PortfolioAsset.objects.create(
            portfolio=self.portfolio,
            symbol='BTC',
            name='Bitcoin',
            percentage=Decimal('50.00'),
            initial_price=Decimal('100000.00'),
            units=Decimal('0.005'),
        )
        self.assertEqual(asset.symbol, 'BTC')
        self.assertEqual(asset.percentage, Decimal('50.00'))
        self.assertEqual(self.portfolio.assets.count(), 1)
