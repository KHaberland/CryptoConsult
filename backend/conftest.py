"""
Общие фикстуры pytest для backend.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def user(db):
    """Обычный пользователь (email — USERNAME_FIELD в users.User)."""
    return User.objects.create_user(
        email="oleg@test.com",
        username="oleg",
        password="strongpass123",
    )


@pytest.fixture
def admin_user(db):
    """Суперпользователь."""
    return User.objects.create_superuser(
        email="admin@test.com",
        username="admin",
        password="adminpass123",
    )


@pytest.fixture
def api_client():
    """APIClient для тестов API."""
    return APIClient()


@pytest.fixture
def auth_client(user, api_client):
    """Авторизованный APIClient."""
    api_client.force_authenticate(user=user)
    return api_client
