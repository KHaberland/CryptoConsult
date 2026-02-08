# CryptoConsult Backend

Django REST API для сервиса Крипто-Консультант.

## Требования

- Python 3.10+
- pip

## Быстрый старт

### 1. Создать виртуальное окружение

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate
```

### 2. Установить зависимости

```powershell
pip install -r requirements.txt
```

### 3. Настроить переменные окружения

Скопируйте `.env.example` в `.env` и заполните значения:

```powershell
copy .env.example .env
```

Отредактируйте `.env`:
```
SECRET_KEY=ваш-секретный-ключ
DEBUG=True
OPENAI_API_KEY=sk-ваш-openai-ключ
```

### 4. Применить миграции

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 5. Создать суперпользователя (опционально)

```powershell
python manage.py createsuperuser
```

### 6. Запустить сервер

```powershell
python manage.py runserver
```

Сервер будет доступен по адресу: http://localhost:8000

## API Endpoints

### Аутентификация

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/auth/register/` | Регистрация пользователя |
| POST | `/api/auth/login/` | Вход (получение JWT токенов) |
| POST | `/api/auth/refresh/` | Обновление access токена |
| GET | `/api/auth/me/` | Информация о текущем пользователе |

### Профиль инвестора

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/profile/` | Получить профиль инвестора |
| POST | `/api/profile/` | Создать профиль (заполнить анкету) |
| PATCH | `/api/profile/` | Обновить профиль |

### Портфель

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/portfolio/` | Список портфелей |
| POST | `/api/portfolio/` | Создать портфель |
| GET | `/api/portfolio/active/` | Получить активный портфель |
| GET | `/api/portfolio/value/` | Текущая стоимость портфеля |
| GET | `/api/portfolio/{id}/` | Детали портфеля |
| PATCH | `/api/portfolio/{id}/` | Обновить портфель |
| DELETE | `/api/portfolio/{id}/` | Деактивировать портфель |

### Цены криптовалют

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/portfolio/prices/` | Текущие цены (без авторизации) |
| GET | `/api/portfolio/prices/changes/` | Цены с изменением за 24ч |
| GET | `/api/portfolio/prices/market/` | Рыночные данные (капитализация, объёмы) |
| GET | `/api/portfolio/prices/history/{symbol}/` | Исторические цены актива |
| GET | `/api/portfolio/prices/supported/` | Список поддерживаемых активов |

### Чат с консультантом

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/chat/` | Отправить сообщение консультанту |
| GET | `/api/chat/history/` | История сообщений |
| DELETE | `/api/chat/history/` | Очистить историю |
| GET | `/api/chat/summary/` | Сводка по портфелю от ИИ |
| GET | `/api/chat/risk/` | Анализ рисков портфеля |
| GET | `/api/chat/alert/` | Проверка алерта о просадке |
| GET | `/api/chat/commands/` | Список быстрых команд |

#### Быстрые команды чата

В чате поддерживаются быстрые команды (можно отправлять с `/` или без):

| Команда | Описание |
|---------|----------|
| `/status` | Текущий статус портфеля |
| `/recommendation` | Рекомендация по портфелю |
| `/risk` | Анализ рисков |
| `/market` | Ситуация на рынке |
| `/drawdown` | Анализ просадки |
| `/rebalance` | Нужна ли перебалансировка |
| `/dca` | Когда делать следующую покупку |
| `/exit` | Стоит ли фиксировать прибыль |

## Примеры запросов

### Регистрация

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "user",
    "password": "securepassword123",
    "password_confirm": "securepassword123"
  }'
```

### Вход

```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

### Создание профиля инвестора

```bash
curl -X POST http://localhost:8000/api/profile/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "investment_horizon": 3,
    "investment_amount": 10000,
    "max_drawdown": 30,
    "needs_liquidity": false,
    "experience_level": "beginner",
    "use_dca": true,
    "dca_parts": 4,
    "use_default_portfolio": true
  }'
```

### Создание портфеля

```bash
curl -X POST http://localhost:8000/api/portfolio/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "name": "Мой первый портфель",
    "initial_amount": 10000,
    "target_years": 3,
    "use_default_assets": true
  }'
```

### Отправка сообщения консультанту

```bash
# Обычное сообщение
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "message": "Какая сейчас ситуация на рынке криптовалют?"
  }'

# Быстрая команда
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "message": "/status"
  }'
```

### Анализ рисков

```bash
curl http://localhost:8000/api/chat/risk/ \
  -H "Authorization: Bearer <access_token>"
```

### Проверка алерта о просадке

```bash
curl http://localhost:8000/api/chat/alert/ \
  -H "Authorization: Bearer <access_token>"
```

### Список быстрых команд

```bash
curl http://localhost:8000/api/chat/commands/
```

### Получение цен криптовалют

```bash
# Все поддерживаемые активы
curl http://localhost:8000/api/portfolio/prices/

# Конкретные активы
curl "http://localhost:8000/api/portfolio/prices/?symbols=BTC,ETH,SOL"

# Цены с изменениями за 24ч
curl "http://localhost:8000/api/portfolio/prices/changes/?symbols=BTC,ETH"

# Рыночные данные
curl "http://localhost:8000/api/portfolio/prices/market/?symbols=BTC,ETH,SOL"

# Исторические цены (30 дней)
curl http://localhost:8000/api/portfolio/prices/history/BTC/

# Исторические цены (90 дней)
curl "http://localhost:8000/api/portfolio/prices/history/ETH/?days=90"

# Список поддерживаемых активов
curl http://localhost:8000/api/portfolio/prices/supported/
```

## Структура проекта

```
backend/
├── config/              # Настройки Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── users/               # Приложение пользователей
│   ├── models.py        # User, InvestorProfile
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── portfolios/          # Приложение портфелей
│   ├── models.py        # Portfolio, PortfolioAsset
│   ├── serializers.py
│   ├── views.py
│   ├── services.py      # PriceService
│   └── urls.py
├── advisor/             # Приложение консультанта
│   ├── models.py        # ChatMessage
│   ├── serializers.py
│   ├── views.py
│   ├── services.py      # AIAdvisorService
│   └── urls.py
├── manage.py
├── requirements.txt
└── .env.example
```

## Админ-панель

Доступна по адресу: http://localhost:8000/admin/

Для входа используйте учётные данные суперпользователя.
