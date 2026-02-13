# Крипто-Консультант

Сервис для долгосрочного инвестирования в криптовалюты с управляемым риском.

## Описание

**Крипто-Консультант** — это персональный ИИ-ассистент, который помогает:
- Составить инвестиционный профиль на основе ваших целей и толерантности к риску
- Сформировать диверсифицированный криптопортфель
- Отслеживать состояние портфеля в реальном времени
- Получать рекомендации по стратегии и управлению рисками
- Контролировать просадку и получать алерты

## Архитектура

```
CryptoConsult/
├── backend/          # Django REST API
│   ├── config/       # Настройки Django
│   ├── users/        # Пользователи и профили
│   ├── portfolios/   # Портфели и цены
│   └── advisor/      # ИИ-консультант
└── frontend/         # Next.js приложение
    └── src/
        ├── app/      # Страницы
        ├── components/
        ├── services/
        └── store/
```

## Быстрый старт

### Требования

- Python 3.10+
- Node.js 18+
- OpenAI API ключ

### 1. Backend

```powershell
cd backend

# Создать виртуальное окружение
python -m venv venv
.\venv\Scripts\Activate

# Установить зависимости
pip install -r requirements.txt

# Настроить .env
copy .env.example .env
# Отредактировать .env, добавить OPENAI_API_KEY

# Применить миграции
python manage.py makemigrations
python manage.py migrate

# Запустить сервер
python manage.py runserver
```

Backend доступен на: http://localhost:8000

### 2. Frontend

```powershell
cd frontend

# Установить зависимости
npm install

# Настроить .env
copy .env.example .env.local

# Запустить сервер разработки
npm run dev
```

Frontend доступен на: http://localhost:3000

## Функционал

### Анкета инвестора (10 вопросов)
1. Горизонт инвестирования (1-7 лет)
2. Сумма инвестиций ($1,000-$50,000)
3. Допустимая просадка (5-50%)
4. Потребность в ликвидности
5. Опыт инвестирования
6. Использование DCA
7. Количество частей DCA
8. Использование базового портфеля

### Базовый портфель
| Актив | Доля |
|-------|------|
| Bitcoin (BTC) | 50% |
| Ethereum (ETH) | 25% |
| BNB | 7.5% |
| Solana (SOL) | 7.5% |
| USDT | 10% |

### ИИ-консультант

Быстрые команды:
- `/status` — текущий статус портфеля
- `/recommendation` — рекомендация по действиям
- `/risk` — анализ рисков
- `/market` — ситуация на рынке
- `/drawdown` — анализ просадки
- `/dca` — когда делать следующую покупку
- `/rebalance` — нужна ли реструктуризация

### Алерты

Система автоматически предупреждает:
- **Warning** — просадка 80% от допустимого уровня
- **Critical** — просадка превысила допустимый уровень

## API

### Аутентификация
- `POST /api/auth/register/` — регистрация
- `POST /api/auth/login/` — вход
- `POST /api/auth/refresh/` — обновление токена
- `GET /api/auth/me/` — текущий пользователь

### Профиль
- `GET/POST/PATCH /api/profile/` — профиль инвестора

### Портфель
- `GET/POST /api/portfolio/` — список/создание портфелей
- `GET /api/portfolio/active/` — активный портфель
- `GET /api/portfolio/value/` — стоимость портфеля

### Цены
- `GET /api/portfolio/prices/` — текущие цены
- `GET /api/portfolio/prices/changes/` — цены с 24ч изменением
- `GET /api/portfolio/prices/market/` — рыночные данные

### Чат
- `POST /api/chat/` — отправить сообщение
- `GET /api/chat/history/` — история
- `GET /api/chat/risk/` — анализ рисков
- `GET /api/chat/alert/` — проверка алерта

## Технологии

### Backend
- Django 4.2
- Django REST Framework
- JWT аутентификация
- OpenAI API
- CoinGecko API

### Frontend
- Next.js 14
- TypeScript
- Tailwind CSS
- Zustand
- Axios

## Лицензия

MIT
