"""
Тесты API профиля инвестора (анкета нового пользователя).
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import InvestorProfile
from portfolios.models import FiatCashFlow, Portfolio, PortfolioAsset


class InvestorProfileAPITests(TestCase):
    """Тесты создания и валидации профиля инвестора."""

    def setUp(self):
        self.client = APIClient()
        self.session_id = str(uuid.uuid4())
        self.profile_url = '/api/profile/'

    def _headers(self):
        return {'HTTP_X_SESSION_ID': self.session_id}

    def _valid_profile_data(self, **overrides):
        data = {
            'name': 'ТестовыйПользователь',
            'investment_horizon': 3,
            'investment_amount': 5000,
            'max_drawdown': 10,  # beginner: макс 10%
            'needs_liquidity': True,
            'experience_level': 'beginner',
            'use_dca': True,
            'dca_parts': 3,
            'use_default_portfolio': True,
        }
        data.update(overrides)
        return data

    def test_create_profile_success_beginner(self):
        """Создание профиля для новичка — успех."""
        data = self._valid_profile_data()
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(InvestorProfile.objects.filter(session_id=self.session_id).exists())
        profile = InvestorProfile.objects.get(session_id=self.session_id)
        self.assertEqual(profile.name, 'ТестовыйПользователь')
        self.assertEqual(profile.investment_horizon, 3)
        self.assertEqual(profile.investment_amount, 5000)
        self.assertEqual(profile.experience_level, 'beginner')
        self.assertEqual(profile.dca_parts, 3)

    def test_create_profile_success_advanced(self):
        """Создание профиля для продвинутого — без DCA."""
        data = self._valid_profile_data(
            experience_level='advanced',
            investment_horizon=7,
            investment_amount=30000,
            use_dca=False,
            dca_parts=None,
        )
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = InvestorProfile.objects.get(session_id=self.session_id)
        self.assertEqual(profile.use_dca, False)
        self.assertIsNone(profile.dca_parts)

    def test_create_profile_duplicate_session_rejected(self):
        """Повторное создание профиля для той же сессии — ошибка."""
        data = self._valid_profile_data()
        first = self.client.post(self.profile_url, data, format='json', **self._headers())
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)

    def test_create_profile_empty_name_rejected(self):
        """Пустое имя — ошибка валидации."""
        data = self._valid_profile_data(name='')
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_create_profile_duplicate_name_rejected(self):
        """Дубликат имени — ошибка валидации."""
        other_session = str(uuid.uuid4())
        InvestorProfile.objects.create(
            session_id=other_session,
            name='СуществующийПользователь',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=20,
        )
        data = self._valid_profile_data(name='СуществующийПользователь')
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_create_profile_invalid_horizon_rejected(self):
        """Горизонт вне 1–7 лет — ошибка."""
        data = self._valid_profile_data(investment_horizon=10)
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('investment_horizon', response.data)

    def test_create_profile_amount_below_minimum_rejected(self):
        """Сумма меньше $1000 — ошибка."""
        data = self._valid_profile_data(investment_amount=500)
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('investment_amount', response.data)

    def test_create_profile_beginner_horizon_limit(self):
        """Новичок: горизонт ограничен 3 годами."""
        data = self._valid_profile_data(
            experience_level='beginner',
            investment_horizon=5,
        )
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('investment_horizon', response.data)

    def test_create_profile_beginner_amount_limit(self):
        """Новичок: сумма ограничена $5000."""
        data = self._valid_profile_data(
            experience_level='beginner',
            investment_amount=10000,
        )
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('investment_amount', response.data)

    def test_create_profile_beginner_drawdown_limit(self):
        """Новичок: просадка ограничена 10%."""
        data = self._valid_profile_data(
            experience_level='beginner',
            max_drawdown=30,
        )
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('max_drawdown', response.data)

    def test_get_profile_after_create(self):
        """Получение профиля после создания."""
        data = self._valid_profile_data()
        self.client.post(self.profile_url, data, format='json', **self._headers())
        response = self.client.get(self.profile_url, **self._headers())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'ТестовыйПользователь')

    def test_get_profile_not_found(self):
        """Профиль не найден — 404."""
        response = self.client.get(self.profile_url, **self._headers())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_profile_use_dca_without_parts_sets_default(self):
        """При use_dca=True и отсутствии dca_parts — устанавливается по уровню опыта."""
        data = self._valid_profile_data(
            experience_level='medium',
            use_dca=True,
            dca_parts=None,  # не передаём
        )
        response = self.client.post(
            self.profile_url,
            data,
            format='json',
            **self._headers()
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        profile = InvestorProfile.objects.get(session_id=self.session_id)
        # medium: dca_parts_min=4
        self.assertEqual(profile.dca_parts, 4)


class ProfileLookupAPITests(TestCase):
    """Тесты поиска профиля по имени (логин)."""

    def setUp(self):
        self.client = APIClient()
        self.lookup_url = '/api/profile/lookup/'

    def test_lookup_empty_name_rejected(self):
        """Пустое имя — 400."""
        response = self.client.get(self.lookup_url, {'name': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lookup_not_found_404(self):
        """Профиль не найден — 404."""
        response = self.client.get(self.lookup_url, {'name': 'НесуществующийПользователь'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('exists', response.data)
        self.assertFalse(response.data['exists'])

    def test_lookup_found_200(self):
        """Профиль найден — 200 с session_id."""
        session_id = str(uuid.uuid4())
        InvestorProfile.objects.create(
            session_id=session_id,
            name='НайденныйПользователь',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
        )
        response = self.client.get(self.lookup_url, {'name': 'НайденныйПользователь'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], session_id)
        self.assertEqual(response.data['name'], 'НайденныйПользователь')

    @patch('advisor.services.PriceService.get_prices_in_currency')
    def test_lookup_uses_fiat_pnl_when_cash_flows_exist(self, mock_prices):
        """Welcome/lookup: при FiatCashFlow — P&L по фиату, не legacy DCA."""
        mock_prices.return_value = {'BTC': 3619.0}
        session_id = str(uuid.uuid4())
        InvestorProfile.objects.create(
            session_id=session_id,
            name='Real',
            investment_horizon=3,
            investment_amount=5000,
            max_drawdown=10,
        )
        portfolio = Portfolio.objects.create(
            session_id=session_id,
            name='Мой портфель (импорт)',
            initial_amount=Decimal('4656.81'),
            target_years=5,
            is_active=True,
        )
        PortfolioAsset.objects.create(
            portfolio=portfolio,
            symbol='BTC',
            name='Bitcoin',
            percentage=Decimal('100'),
            initial_price=Decimal('80000'),
            units=Decimal('1'),
            is_recommended=True,
        )
        FiatCashFlow.objects.create(
            portfolio=portfolio,
            kind=FiatCashFlow.KIND_DEPOSIT,
            amount=Decimal('3386.33'),
            currency='USD',
            fx_rate_to_base=Decimal('1'),
            occurred_on=date.today(),
        )

        response = self.client.get(self.lookup_url, {'name': 'Real'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        p = response.data['portfolio']
        self.assertTrue(p['use_fiat_pnl'])
        self.assertAlmostEqual(p['cash_in_total'], 3386.33, places=2)
        self.assertAlmostEqual(p['current_value'], 3619.0, places=2)
        self.assertGreater(p['profit_loss'], 0)
        self.assertGreater(p['profit_loss_percent'], 0)
        # Legacy initial_value был бы ~4656 — не должен «просачиваться».
        self.assertLess(p['initial_value'], 4000)
        self.assertEqual(response.data['analysis']['status'], 'profit')
