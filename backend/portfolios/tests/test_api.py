"""
Тесты API портфеля (создание после анкеты).
"""

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from portfolios.models import Portfolio, PortfolioAsset
from users.models import InvestorProfile


# Мок активов для портфеля (без внешних API)
MOCK_DEFAULT_ASSETS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 25.0},
    {'symbol': 'BNB', 'name': 'BNB', 'percentage': 7.5},
    {'symbol': 'SOL', 'name': 'Solana', 'percentage': 7.5},
    {'symbol': 'USDT', 'name': 'Tether', 'percentage': 10.0},
]

MOCK_BEGINNER_ASSETS = [
    {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
    {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 30.0},
    {'symbol': 'USDT', 'name': 'Tether', 'percentage': 10.0},
    {'symbol': 'XRP', 'name': 'XRP', 'percentage': 2.0},
    {'symbol': 'BNB', 'name': 'BNB', 'percentage': 2.0},
    {'symbol': 'SOL', 'name': 'Solana', 'percentage': 2.0},
    {'symbol': 'DOGE', 'name': 'Dogecoin', 'percentage': 2.0},
    {'symbol': 'ADA', 'name': 'Cardano', 'percentage': 2.0},
]

MOCK_PRICES = {
    'BTC': 100000.0,
    'ETH': 3500.0,
    'BNB': 700.0,
    'SOL': 250.0,
    'USDT': 1.0,
    'XRP': 3.0,
    'DOGE': 0.4,
    'ADA': 1.0,
}


class PortfolioAPITests(TestCase):
    """Тесты создания портфеля после анкеты."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.portfolio_url = '/api/portfolio/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _create_profile(self):
        """Создать профиль для сессии (как после анкеты)."""
        InvestorProfile.objects.create(
            session_id=self.session_id,
            name='ТестовыйПользователь',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
            experience_level='beginner',
            use_dca=True,
            dca_parts=3,
            use_default_portfolio=True,
        )

    @patch('portfolios.serializers.PriceService')
    def test_create_portfolio_success_default(self, mock_price_class):
        """Создание портфеля с базовыми активами — успех."""
        mock_service = MagicMock()
        mock_service.get_prices.return_value = MOCK_PRICES
        mock_service.get_beginner_portfolio_assets.return_value = MOCK_BEGINNER_ASSETS
        mock_service.get_some_experience_portfolio_assets.return_value = MOCK_DEFAULT_ASSETS
        mock_service.is_symbol_supported.return_value = True
        mock_price_class.return_value = mock_service

        data = {
            'name': 'Мой портфель',
            'initial_amount': 1666.67,  # 5000/3 для DCA
            'target_years': 3,
            'use_default_assets': True,
            'experience_level': 'beginner',
        }
        response = self.client.post(
            self.portfolio_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Portfolio.objects.filter(session_id=self.session_id).exists())
        portfolio = Portfolio.objects.get(session_id=self.session_id)
        self.assertAlmostEqual(float(portfolio.initial_amount), 1666.67, places=2)
        self.assertEqual(portfolio.target_years, 3)
        self.assertGreater(portfolio.assets.count(), 0)

    @patch('portfolios.serializers.PriceService')
    def test_create_portfolio_amount_below_minimum_rejected(self, mock_price_class):
        """Сумма меньше $1000 — ошибка."""
        data = {
            'name': 'Мой портфель',
            'initial_amount': 500,
            'target_years': 3,
            'use_default_assets': True,
        }
        response = self.client.post(
            self.portfolio_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('initial_amount', response.data)

    @patch('portfolios.serializers.PriceService')
    def test_create_portfolio_invalid_target_years_rejected(self, mock_price_class):
        """Горизонт вне 1–7 лет — ошибка."""
        data = {
            'name': 'Мой портфель',
            'initial_amount': 5000,
            'target_years': 10,
            'use_default_assets': True,
        }
        response = self.client.post(
            self.portfolio_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('target_years', response.data)

    @patch('portfolios.serializers.PriceService')
    def test_create_portfolio_duplicate_active_rejected(self, mock_price_class):
        """Повторное создание при активном портфеле — ошибка."""
        mock_service = MagicMock()
        mock_service.get_prices.return_value = MOCK_PRICES
        mock_service.get_beginner_portfolio_assets.return_value = MOCK_BEGINNER_ASSETS
        mock_service.get_some_experience_portfolio_assets.return_value = MOCK_DEFAULT_ASSETS
        mock_service.is_symbol_supported.return_value = True
        mock_price_class.return_value = mock_service

        data = {
            'name': 'Мой портфель',
            'initial_amount': 5000,
            'target_years': 3,
            'use_default_assets': True,
            'experience_level': 'beginner',
        }
        self.client.post(self.portfolio_url, data, format='json', **self._headers())
        response = self.client.post(
            self.portfolio_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    @patch('portfolios.serializers.PriceService')
    def test_full_flow_profile_then_portfolio(self, mock_price_class):
        """Полный сценарий: профиль → портфель (как после анкеты)."""
        mock_service = MagicMock()
        mock_service.get_prices.return_value = MOCK_PRICES
        mock_service.get_beginner_portfolio_assets.return_value = MOCK_BEGINNER_ASSETS
        mock_service.get_some_experience_portfolio_assets.return_value = MOCK_DEFAULT_ASSETS
        mock_service.is_symbol_supported.return_value = True
        mock_price_class.return_value = mock_service

        # 1. Создаём профиль (как после анкеты)
        profile_data = {
            'name': 'НовыйИнвестор',
            'investment_horizon': 3,
            'investment_amount': 5000,
            'max_drawdown': 10,
            'needs_liquidity': True,
            'experience_level': 'beginner',
            'use_dca': True,
            'dca_parts': 3,
            'use_default_portfolio': True,
        }
        profile_resp = self.client.post(
            '/api/profile/',
            profile_data,
            format='json',
            **self._headers()
        )
        self.assertEqual(profile_resp.status_code, status.HTTP_201_CREATED)

        # 2. Создаём портфель (первая часть DCA)
        portfolio_data = {
            'name': 'Мой портфель',
            'initial_amount': 1666.67,
            'target_years': 3,
            'use_default_assets': True,
            'experience_level': 'beginner',
        }
        portfolio_resp = self.client.post(
            self.portfolio_url,
            portfolio_data,
            format='json',
            **self._headers()
        )
        self.assertEqual(portfolio_resp.status_code, status.HTTP_201_CREATED)

        # 3. Проверяем, что портфель и профиль связаны одной сессией
        profile = InvestorProfile.objects.get(session_id=self.session_id)
        portfolio = Portfolio.objects.get(session_id=self.session_id)
        self.assertEqual(profile.name, 'НовыйИнвестор')
        self.assertEqual(portfolio.name, 'Мой портфель')
        self.assertGreater(portfolio.assets.count(), 0)
