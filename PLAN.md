# План разработки MVP Крипто-Консультант

> Документ описывает последовательность этапов разработки проекта на основе [PROJECT.md](./PROJECT.md)

---

## 📋 Обзор этапов

| Этап | Название | Статус |
|------|----------|--------|
| 0 | Подготовка окружения | 🔲 Не начат |
| 1 | Базовый функционал | 🔲 Не начат |
| 2 | Интеграции | 🔲 Не начат |
| 3 | Аналитика | 🔲 Не начат |
| 4 | Оптимизация | 🔲 Не начат |

---

## Этап 0: Подготовка окружения

### 0.1 Инициализация репозитория

- [ ] Создать структуру папок проекта
- [ ] Настроить `.gitignore` для Python, Node.js, IDE
- [ ] Создать `docker-compose.yml` для локальной разработки
- [ ] Настроить pre-commit hooks (black, flake8, eslint)

**Структура проекта:**

```
CryptoConsult/
├── backend/                 # Django REST API
│   ├── config/              # Настройки Django
│   ├── apps/
│   │   ├── users/           # Пользователи и аутентификация
│   │   ├── portfolios/      # Портфели и активы
│   │   ├── sessions/        # Сессии анкетирования
│   │   └── ai_advisor/      # Интеграция с LLM
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Next.js приложение
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── PROJECT.md
├── PLAN.md
└── README.md
```

### 0.2 Настройка Backend

- [ ] Инициализировать Django-проект
- [ ] Установить Django REST Framework
- [ ] Настроить PostgreSQL подключение
- [ ] Настроить Redis подключение
- [ ] Настроить Celery
- [ ] Создать базовые модели (`User`, `Portfolio`, `Session`, `Message`)

**Зависимости (`requirements.txt`):**

```
Django>=4.2
djangorestframework>=3.14
psycopg2-binary>=2.9
redis>=5.0
celery>=5.3
django-cors-headers>=4.3
python-dotenv>=1.0
openai>=1.0  # или anthropic для Claude
```

### 0.3 Настройка Frontend

- [ ] Инициализировать Next.js проект (TypeScript)
- [ ] Настроить Tailwind CSS
- [ ] Установить UI-библиотеку (shadcn/ui или Ant Design)
- [ ] Настроить axios/fetch для API-запросов
- [ ] Создать базовую структуру компонентов

**Зависимости (`package.json`):**

```json
{
  "dependencies": {
    "next": "^14.0",
    "react": "^18.0",
    "axios": "^1.6",
    "tailwindcss": "^3.4",
    "recharts": "^2.10",
    "zustand": "^4.4"
  }
}
```

### 0.4 Docker-окружение

- [ ] Dockerfile для backend
- [ ] Dockerfile для frontend
- [ ] docker-compose.yml с сервисами:
  - `backend` (Django)
  - `frontend` (Next.js)
  - `db` (PostgreSQL)
  - `redis` (Redis)
  - `celery` (Celery worker)
  - `celery-beat` (Celery scheduler)

**Критерии готовности этапа 0:**
- ✅ `docker-compose up` запускает все сервисы
- ✅ Backend доступен на `http://localhost:8000`
- ✅ Frontend доступен на `http://localhost:3000`
- ✅ Миграции применяются без ошибок

---

## Этап 1: Базовый функционал

### 1.1 Регистрация и аутентификация

**Backend задачи:**

- [ ] Модель `User` с полями:
  - `email` (unique)
  - `password` (hashed)
  - `created_at`
  - `experience_level` (новичок/немного опыта/средний/продвинутый)
- [ ] API endpoints:
  - `POST /api/auth/register/` — регистрация
  - `POST /api/auth/login/` — авторизация (JWT)
  - `POST /api/auth/logout/` — выход
  - `GET /api/auth/me/` — текущий пользователь
- [ ] JWT-аутентификация (djangorestframework-simplejwt)
- [ ] Валидация email и пароля

**Frontend задачи:**

- [ ] Страница `/register` — форма регистрации
- [ ] Страница `/login` — форма входа
- [ ] Хранение токена (localStorage / httpOnly cookie)
- [ ] Защищённые маршруты (redirect на login)
- [ ] Компонент `AuthProvider` для контекста авторизации

**Критерии готовности:**
- ✅ Пользователь может зарегистрироваться
- ✅ Пользователь может войти и выйти
- ✅ Защищённые страницы недоступны без авторизации

---

### 1.2 Анкета инвестора (10 вопросов)

**Backend задачи:**

- [ ] Модель `InvestorProfile`:
  ```python
  class InvestorProfile(models.Model):
      user = models.OneToOneField(User)
      investment_horizon = models.IntegerField()      # Вопрос 1: 1-7 лет
      investment_amount = models.DecimalField()       # Вопрос 2: сумма
      max_drawdown = models.IntegerField()            # Вопрос 3: % просадки
      needs_liquidity = models.BooleanField()         # Вопрос 4
      experience_level = models.CharField()           # Вопрос 5
      use_dca = models.BooleanField()                 # Вопрос 7
      dca_parts = models.IntegerField(null=True)      # 3-6 частей
      use_default_portfolio = models.BooleanField()   # Вопрос 8
      notification_frequency = models.CharField()     # Вопрос 9
      created_at = models.DateTimeField()
      updated_at = models.DateTimeField()
  ```
- [ ] API endpoints:
  - `POST /api/profile/` — сохранить анкету
  - `GET /api/profile/` — получить анкету
  - `PATCH /api/profile/` — обновить анкету
- [ ] Валидация ответов:
  - Горизонт: 1–7 лет
  - Сумма: $1,000–$50,000
  - Просадка: 5–50%

**Frontend задачи:**

- [ ] Компонент `QuestionnaireWizard` — пошаговая анкета
- [ ] Компоненты для каждого типа вопроса:
  - `SliderQuestion` — для горизонта и просадки
  - `NumberInput` — для суммы
  - `RadioQuestion` — для выбора вариантов
  - `CheckboxQuestion` — для множественного выбора
- [ ] Прогресс-бар (шаг X из 10)
- [ ] Валидация на клиенте
- [ ] Сохранение черновика в localStorage
- [ ] Комментарии сервиса после каждого ответа

**Критерии готовности:**
- ✅ Пользователь проходит все 10 вопросов
- ✅ Ответы сохраняются в БД
- ✅ Валидация работает корректно

---

### 1.3 Создание и сохранение портфеля

**Backend задачи:**

- [ ] Модель `Portfolio`:
  ```python
  class Portfolio(models.Model):
      user = models.ForeignKey(User)
      name = models.CharField()
      initial_amount = models.DecimalField()
      start_date = models.DateField()
      target_end_date = models.DateField()
      is_active = models.BooleanField(default=True)
  ```
- [ ] Модель `PortfolioAsset`:
  ```python
  class PortfolioAsset(models.Model):
      portfolio = models.ForeignKey(Portfolio)
      symbol = models.CharField()           # BTC, ETH, etc.
      target_percentage = models.DecimalField()
      current_amount = models.DecimalField()
  ```
- [ ] Базовый портфель по умолчанию:
  - BTC: 50%
  - ETH: 25%
  - BNB: 7.5%
  - SOL: 7.5%
  - USDT/USDC: 10%
- [ ] API endpoints:
  - `POST /api/portfolios/` — создать портфель
  - `GET /api/portfolios/` — список портфелей
  - `GET /api/portfolios/{id}/` — детали портфеля
  - `PATCH /api/portfolios/{id}/` — обновить портфель
  - `POST /api/portfolios/{id}/assets/` — добавить актив

**Frontend задачи:**

- [ ] Страница `/portfolio/create` — создание портфеля
- [ ] Компонент `AssetAllocation` — распределение активов (pie chart)
- [ ] Возможность кастомизации портфеля (добавить 1-2 альткойна)
- [ ] Подтверждение создания портфеля

**Критерии готовности:**
- ✅ Портфель создаётся на основе анкеты
- ✅ Активы распределены согласно стратегии
- ✅ Портфель привязан к пользователю

---

### 1.4 Базовый дашборд

**Backend задачи:**

- [ ] API endpoint `GET /api/dashboard/` возвращает:
  ```json
  {
    "portfolio": {
      "total_value": 10000,
      "initial_value": 10000,
      "profit_loss": 0,
      "profit_loss_percent": 0,
      "start_date": "2026-01-25",
      "target_date": "2029-01-25",
      "days_remaining": 1095
    },
    "assets": [
      {"symbol": "BTC", "percentage": 50, "value": 5000},
      {"symbol": "ETH", "percentage": 25, "value": 2500}
    ],
    "strategy": {
      "horizon_years": 3,
      "max_drawdown": 30,
      "uses_dca": true
    }
  }
  ```

**Frontend задачи:**

- [ ] Страница `/dashboard` — главная страница после входа
- [ ] Компоненты:
  - `PortfolioSummary` — общая стоимость, прибыль/убыток
  - `AssetList` — список активов с процентами
  - `StrategyInfo` — параметры стратегии
  - `TimelineProgress` — прогресс до целевой даты
- [ ] Responsive дизайн (mobile-first)

**Критерии готовности:**
- ✅ Дашборд отображает актуальные данные портфеля
- ✅ UI интуитивно понятен
- ✅ Страница адаптивна для мобильных устройств

---

## Этап 2: Интеграции

### 2.1 Интеграция с API криптобирж

**Backend задачи:**

- [ ] Сервис `PriceService` для получения цен:
  ```python
  class PriceService:
      def get_current_prices(self, symbols: list) -> dict
      def get_historical_prices(self, symbol: str, days: int) -> list
  ```
- [ ] Интеграция с CoinGecko API (бесплатный tier)
- [ ] Альтернатива: Binance API для более точных данных
- [ ] Кэширование цен в Redis (TTL: 1 минута)
- [ ] Celery task для периодического обновления цен
- [ ] Модель `PriceHistory` для хранения исторических данных

**Endpoints CoinGecko:**

```
GET https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd
GET https://api.coingecko.com/api/v3/coins/{id}/market_chart?vs_currency=usd&days=30
```

**Критерии готовности:**
- ✅ Цены обновляются автоматически
- ✅ Кэш работает корректно
- ✅ Портфель пересчитывается при изменении цен

---

### 2.2 Подключение LLM для рекомендаций

**Backend задачи:**

- [ ] Сервис `AIAdvisorService`:
  ```python
  class AIAdvisorService:
      def get_recommendation(self, portfolio, market_data, user_profile) -> str
      def analyze_drawdown(self, portfolio, current_drawdown) -> str
      def generate_monthly_report(self, portfolio) -> str
  ```
- [ ] Промпт-шаблоны для разных сценариев:
  - Рекомендация по запросу пользователя
  - Предупреждение о просадке
  - Ежемесячный отчёт
  - Рекомендация после 12 месяцев
- [ ] Модель `Message` для хранения истории диалога:
  ```python
  class Message(models.Model):
      user = models.ForeignKey(User)
      portfolio = models.ForeignKey(Portfolio)
      role = models.CharField()  # user / assistant
      content = models.TextField()
      created_at = models.DateTimeField()
  ```
- [ ] API endpoints:
  - `POST /api/chat/` — отправить сообщение
  - `GET /api/chat/history/` — история сообщений
- [ ] Адаптация детализации ответа по уровню опыта пользователя

**Пример промпта:**

```
Ты — крипто-консультант для долгосрочных инвесторов.

Профиль инвестора:
- Горизонт: {horizon} лет
- Максимальная просадка: {max_drawdown}%
- Опыт: {experience_level}

Текущий портфель:
{portfolio_summary}

Текущая рыночная ситуация:
{market_summary}

Дай рекомендацию на основе этих данных. 
Для {experience_level} пользователя используй {detail_level} объяснения.
```

**Frontend задачи:**

- [ ] Компонент `ChatInterface` — чат с консультантом
- [ ] Отображение рекомендаций с форматированием
- [ ] История сообщений
- [ ] Индикатор загрузки при генерации ответа

**Критерии готовности:**
- ✅ LLM генерирует релевантные рекомендации
- ✅ Контекст портфеля передаётся корректно
- ✅ История сообщений сохраняется

---

### 2.3 Система уведомлений

**Backend задачи:**

- [ ] Модель `Notification`:
  ```python
  class Notification(models.Model):
      user = models.ForeignKey(User)
      type = models.CharField()  # monthly_report / drawdown_alert / recommendation
      title = models.CharField()
      content = models.TextField()
      is_read = models.BooleanField(default=False)
      created_at = models.DateTimeField()
  ```
- [ ] Celery Beat tasks:
  - `generate_monthly_reports` — ежемесячные отчёты
  - `check_drawdown_alerts` — проверка просадок (ежедневно)
  - `check_12_month_milestone` — проверка 12-месячного срока
- [ ] API endpoints:
  - `GET /api/notifications/` — список уведомлений
  - `PATCH /api/notifications/{id}/read/` — отметить прочитанным
- [ ] Email-уведомления (опционально, через SendGrid/Mailgun)

**Frontend задачи:**

- [ ] Компонент `NotificationBell` — иконка с счётчиком
- [ ] Компонент `NotificationList` — список уведомлений
- [ ] Push-уведомления (Web Push API) — опционально

**Критерии готовности:**
- ✅ Ежемесячные отчёты генерируются автоматически
- ✅ Алерты о просадке работают
- ✅ Пользователь видит уведомления в интерфейсе

---

## Этап 3: Аналитика

### 3.1 Расчёт просадок и предупреждения

**Backend задачи:**

- [ ] Сервис `DrawdownService`:
  ```python
  class DrawdownService:
      def calculate_current_drawdown(self, portfolio) -> float
      def get_max_historical_drawdown(self, portfolio) -> float
      def check_drawdown_threshold(self, portfolio) -> bool
  ```
- [ ] Логика расчёта просадки:
  ```
  drawdown = (peak_value - current_value) / peak_value * 100
  ```
- [ ] Хранение пиковых значений портфеля
- [ ] Триггер алерта при превышении допустимой просадки
- [ ] Рекомендации при срабатывании алерта:
  - Продолжить удержание
  - Перевести часть в стейблы

**Frontend задачи:**

- [ ] Компонент `DrawdownAlert` — предупреждение о просадке
- [ ] Визуализация текущей просадки (gauge chart)
- [ ] Кнопки действий при алерте

**Критерии готовности:**
- ✅ Просадка рассчитывается корректно
- ✅ Алерт срабатывает при превышении порога
- ✅ Пользователь может выбрать действие

---

### 3.2 Визуализация динамики портфеля

**Backend задачи:**

- [ ] Модель `PortfolioSnapshot`:
  ```python
  class PortfolioSnapshot(models.Model):
      portfolio = models.ForeignKey(Portfolio)
      total_value = models.DecimalField()
      assets_breakdown = models.JSONField()  # {BTC: 5000, ETH: 2500, ...}
      recorded_at = models.DateTimeField()
  ```
- [ ] Celery task для ежедневных снапшотов
- [ ] API endpoint `GET /api/portfolios/{id}/history/`:
  ```json
  {
    "data": [
      {"date": "2026-01-25", "value": 10000},
      {"date": "2026-01-26", "value": 10150},
      ...
    ],
    "initial_value": 10000,
    "current_value": 12850,
    "profit_loss_percent": 28.5
  }
  ```

**Frontend задачи:**

- [ ] Компонент `PortfolioChart` — линейный график динамики
- [ ] Фильтры периода: 1M, 3M, 6M, 1Y, All
- [ ] Компонент `AssetBreakdownChart` — pie chart распределения
- [ ] Сравнение с бенчмарком (BTC, ETH)

**Критерии готовности:**
- ✅ График отображает историю портфеля
- ✅ Можно переключать периоды
- ✅ Данные обновляются ежедневно

---

### 3.3 История рекомендаций и действий

**Backend задачи:**

- [ ] Модель `UserAction`:
  ```python
  class UserAction(models.Model):
      user = models.ForeignKey(User)
      portfolio = models.ForeignKey(Portfolio)
      action_type = models.CharField()  # rebalance / exit / hold
      description = models.TextField()
      ai_recommendation = models.ForeignKey(Message, null=True)
      created_at = models.DateTimeField()
  ```
- [ ] API endpoints:
  - `GET /api/actions/` — история действий
  - `POST /api/actions/` — записать действие

**Frontend задачи:**

- [ ] Страница `/history` — история рекомендаций и действий
- [ ] Timeline компонент с событиями
- [ ] Фильтры по типу события

**Критерии готовности:**
- ✅ Все рекомендации и действия логируются
- ✅ Пользователь может просмотреть историю
- ✅ Связь между рекомендацией и действием отслеживается

---

## Этап 4: Оптимизация

### 4.1 A/B тестирование рекомендаций

**Backend задачи:**

- [ ] Модель `Experiment`:
  ```python
  class Experiment(models.Model):
      name = models.CharField()
      variant_a = models.JSONField()  # Параметры варианта A
      variant_b = models.JSONField()  # Параметры варианта B
      is_active = models.BooleanField()
  ```
- [ ] Модель `UserExperiment`:
  ```python
  class UserExperiment(models.Model):
      user = models.ForeignKey(User)
      experiment = models.ForeignKey(Experiment)
      variant = models.CharField()  # A или B
      converted = models.BooleanField(default=False)
  ```
- [ ] Сервис для назначения вариантов
- [ ] Метрики конверсии (следование рекомендациям)

**Критерии готовности:**
- ✅ Пользователи распределяются по вариантам
- ✅ Метрики собираются
- ✅ Можно сравнить эффективность вариантов

---

### 4.2 Персонализация на основе поведения

**Backend задачи:**

- [ ] Сбор поведенческих данных:
  - Частота входов
  - Время просмотра дашборда
  - Реакция на рекомендации
  - История действий
- [ ] Модель `UserBehavior`:
  ```python
  class UserBehavior(models.Model):
      user = models.ForeignKey(User)
      event_type = models.CharField()
      event_data = models.JSONField()
      created_at = models.DateTimeField()
  ```
- [ ] Адаптация рекомендаций на основе поведения
- [ ] Персонализация частоты уведомлений

**Критерии готовности:**
- ✅ Поведение пользователя отслеживается
- ✅ Рекомендации адаптируются
- ✅ Уведомления персонализированы

---

## 📊 Зависимости между этапами

```
Этап 0 ──────────────────────────────────────────────────────────┐
   │                                                              │
   ▼                                                              │
Этап 1.1 (Auth) ─────┬─────────────────────────────────────┐     │
   │                 │                                      │     │
   ▼                 ▼                                      │     │
Этап 1.2 (Анкета)   Этап 1.4 (Дашборд) ◀────────────────┐ │     │
   │                 ▲                                   │ │     │
   ▼                 │                                   │ │     │
Этап 1.3 (Портфель) ─┘                                   │ │     │
   │                                                     │ │     │
   ├─────────────────────────────────────────────────────┼─┼─────┘
   │                                                     │ │
   ▼                                                     │ │
Этап 2.1 (Цены) ────────────────────────────────────────►│ │
   │                                                     │ │
   ▼                                                     │ │
Этап 2.2 (LLM) ◀─────────────────────────────────────────┘ │
   │                                                       │
   ▼                                                       │
Этап 2.3 (Уведомления) ◀───────────────────────────────────┘
   │
   ▼
Этап 3.1 (Просадки) ──► Этап 3.2 (Графики) ──► Этап 3.3 (История)
                                                    │
                                                    ▼
                        Этап 4.1 (A/B) ──► Этап 4.2 (Персонализация)
```

---

## 🔧 Команды разработки

### Локальный запуск

```powershell
# Клонирование и запуск
git clone <repo-url>
cd CryptoConsult

# Запуск через Docker
docker-compose up -d

# Применение миграций
docker-compose exec backend python manage.py migrate

# Создание суперпользователя
docker-compose exec backend python manage.py createsuperuser
```

### Полезные команды

```powershell
# Backend
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py shell

# Frontend
docker-compose exec frontend npm run dev
docker-compose exec frontend npm run build

# Логи
docker-compose logs -f backend
docker-compose logs -f celery

# Тесты
docker-compose exec backend pytest
docker-compose exec frontend npm test
```

---

## ✅ Чек-лист готовности MVP

### Функциональность

- [ ] Регистрация и авторизация работают
- [ ] Анкета из 10 вопросов заполняется
- [ ] Портфель создаётся и отображается
- [ ] Цены активов обновляются
- [ ] LLM генерирует рекомендации
- [ ] Уведомления приходят (ежемесячный отчёт)
- [ ] Алерты о просадке работают
- [ ] Графики динамики портфеля отображаются
- [ ] История рекомендаций сохраняется

### Качество

- [ ] Код покрыт тестами (>70%)
- [ ] Нет критических багов
- [ ] UI/UX проверен на usability
- [ ] Производительность приемлема (<2s загрузка страниц)
- [ ] Безопасность проверена (OWASP Top 10)

### Деплой

- [ ] Приложение развёрнуто на staging
- [ ] CI/CD настроен
- [ ] Мониторинг и логирование работают
- [ ] Документация API актуальна

---

*План создан: 25.01.2026*
*Последнее обновление: 25.01.2026*
