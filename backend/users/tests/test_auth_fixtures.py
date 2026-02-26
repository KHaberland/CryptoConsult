"""
Проверка фикстур аутентификации (user, admin_user, api_client, auth_client).
"""

import pytest


def test_user_fixture(user):
    """Фикстура user создаёт пользователя."""
    assert user.email == "oleg@test.com"
    assert user.username == "oleg"
    assert user.check_password("strongpass123")


def test_admin_user_fixture(admin_user):
    """Фикстура admin_user создаёт суперпользователя."""
    assert admin_user.email == "admin@test.com"
    assert admin_user.is_superuser
    assert admin_user.is_staff


def test_api_client_fixture(api_client):
    """Фикстура api_client возвращает APIClient."""
    assert api_client is not None


def test_auth_client_fixture(auth_client, user):
    """Фикстура auth_client возвращает авторизованный клиент."""
    assert auth_client is not None
    # force_authenticate установлен — запросы идут от имени user
