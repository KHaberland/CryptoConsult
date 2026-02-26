"""
Тесты прав доступа к API портфеля.

Сейчас API использует session_id без авторизации — проверки минимальны.
"""

from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

import uuid


class PortfolioPermissionTests(TestCase):
    """Тесты доступа по session_id."""

    def setUp(self):
        self.client = APIClient()
        self.portfolio_url = '/api/portfolio/'

    def test_create_without_session_id_uses_generated_session(self):
        """Без X-Session-Id middleware генерирует session_id — запрос проходит (201)."""
        with patch('portfolios.serializers.PriceService') as mock_ps:
            mock_ps.return_value.get_prices.return_value = {'BTC': 100000.0, 'ETH': 3500.0}
            mock_ps.return_value.get_beginner_portfolio_assets.return_value = [
                {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
                {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 50.0},
            ]
            mock_ps.return_value.get_some_experience_portfolio_assets.return_value = []
            mock_ps.return_value.is_symbol_supported.return_value = True

            data = {
                'name': 'Портфель',
                'initial_amount': 5000,
                'target_years': 3,
                'use_default_assets': True,
            }
            response = self.client.post(
                self.portfolio_url,
                data,
                format='json',
            )
            # Middleware генерирует session_id — портфель создаётся
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_with_valid_session_id_accepted(self):
        """Создание с валидной сессией и профилем — успех (мок PriceService)."""
        from unittest.mock import patch, MagicMock
        session_id = str(uuid.uuid4())
        from users.models import InvestorProfile
        InvestorProfile.objects.create(
            session_id=session_id,
            name='Тест',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
            use_dca=False,
            use_default_portfolio=True,
        )
        with patch('portfolios.serializers.PriceService') as mock_ps:
            mock_ps.return_value.get_prices.return_value = {'BTC': 100000.0, 'ETH': 3500.0}
            mock_ps.return_value.get_beginner_portfolio_assets.return_value = [
                {'symbol': 'BTC', 'name': 'Bitcoin', 'percentage': 50.0},
                {'symbol': 'ETH', 'name': 'Ethereum', 'percentage': 50.0},
            ]
            mock_ps.return_value.get_some_experience_portfolio_assets.return_value = []
            mock_ps.return_value.is_symbol_supported.return_value = True

            response = self.client.post(
                self.portfolio_url,
                {
                    'name': 'Портфель',
                    'initial_amount': 5000,
                    'target_years': 3,
                    'use_default_assets': True,
                    'experience_level': 'beginner',
                },
                format='json',
                HTTP_X_SESSION_ID=session_id,
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
