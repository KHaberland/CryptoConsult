# PLAN01: Минимальный рабочий MVP

> Цель: создать работающий прототип за минимальное время для валидации концепции

---

## 🎯 Цель минимального MVP

Создать работающий сервис, который:
1. Позволяет пользователю заполнить анкету инвестора
2. Формирует портфель на основе ответов
3. Показывает текущую стоимость портфеля
4. Даёт рекомендации через чат с ИИ

**Что НЕ входит в минимальный MVP:**
- ❌ Email-уведомления
- ❌ Push-уведомления
- ❌ Celery / фоновые задачи
- ❌ Сложная аналитика просадок
- ❌ A/B тестирование
- ❌ Персонализация
- ❌ История графиков портфеля

---

## 📦 Упрощённая архитектура

```
┌─────────────────────┐
│   Frontend          │
│   (Next.js)         │
│                     │
│ - Анкета            │
│ - Дашборд           │
│ - Чат с ИИ          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Backend           │
│   (Django REST)     │
│                     │
│ - API endpoints     │
│ - Логика портфеля   │
│ - Запросы к LLM     │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌─────────┐  ┌─────────┐
│PostgreSQL│  │ LLM API │
│ SQLite  │  │(OpenAI) │
└─────────┘  └─────────┘
     ▲
     │
┌─────────┐
│CoinGecko│
│  API    │
└─────────┘
```

**Упрощения:**
- SQLite вместо PostgreSQL (для старта)
- Без Redis
- Без Celery (синхронные запросы)
- Без Docker (локальный запуск)

---

## 📋 Этапы разработки

### Этап 1: Backend — базовые модели и API

**Задачи:**

- [ ] **1.1** Создать Django проект
  ```powershell
  django-admin startproject config .
  python manage.py startapp users
  python manage.py startapp portfolios
  python manage.py startapp advisor
  ```

- [ ] **1.2** Модель пользователя с профилем инвестора
  ```python
  # users/models.py
  class User(AbstractUser):
      pass

  class InvestorProfile(models.Model):
      user = models.OneToOneField(User, on_delete=models.CASCADE)
      investment_horizon = models.IntegerField()        # 1-7 лет
      investment_amount = models.DecimalField(max_digits=10, decimal_places=2)
      max_drawdown = models.IntegerField()              # 5-50%
      needs_liquidity = models.BooleanField()
      experience_level = models.CharField(max_length=20)
      use_dca = models.BooleanField()
      dca_parts = models.IntegerField(null=True, blank=True)
      created_at = models.DateTimeField(auto_now_add=True)
  ```

- [ ] **1.3** Модель портфеля
  ```python
  # portfolios/models.py
  class Portfolio(models.Model):
      user = models.ForeignKey(User, on_delete=models.CASCADE)
      initial_amount = models.DecimalField(max_digits=10, decimal_places=2)
      start_date = models.DateField(auto_now_add=True)
      target_years = models.IntegerField()
      is_active = models.BooleanField(default=True)

  class PortfolioAsset(models.Model):
      portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
      symbol = models.CharField(max_length=10)  # BTC, ETH, etc.
      percentage = models.DecimalField(max_digits=5, decimal_places=2)
  ```

- [ ] **1.4** Модель для хранения сообщений чата
  ```python
  # advisor/models.py
  class ChatMessage(models.Model):
      user = models.ForeignKey(User, on_delete=models.CASCADE)
      role = models.CharField(max_length=10)  # user / assistant
      content = models.TextField()
      created_at = models.DateTimeField(auto_now_add=True)
  ```

- [ ] **1.5** API endpoints (Django REST Framework)

  | Метод | Endpoint | Описание |
  |-------|----------|----------|
  | POST | `/api/auth/register/` | Регистрация |
  | POST | `/api/auth/login/` | Вход (JWT) |
  | GET | `/api/profile/` | Профиль инвестора |
  | POST | `/api/profile/` | Сохранить анкету |
  | GET | `/api/portfolio/` | Получить портфель |
  | POST | `/api/portfolio/` | Создать портфель |
  | GET | `/api/portfolio/value/` | Текущая стоимость |
  | POST | `/api/chat/` | Отправить сообщение ИИ |
  | GET | `/api/chat/history/` | История чата |

**Файлы для создания:**
```
backend/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── users/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── portfolios/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── services.py      # PriceService
├── advisor/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── services.py      # AIAdvisorService
├── manage.py
└── requirements.txt
```

**requirements.txt:**
```
Django>=4.2
djangorestframework>=3.14
djangorestframework-simplejwt>=5.3
django-cors-headers>=4.3
requests>=2.31
openai>=1.0
python-dotenv>=1.0
```

---

### Этап 2: Сервис получения цен

**Задачи:**

- [ ] **2.1** Создать `PriceService`
  ```python
  # portfolios/services.py
  import requests

  class PriceService:
      COINGECKO_URL = "https://api.coingecko.com/api/v3"
      
      SYMBOL_TO_ID = {
          "BTC": "bitcoin",
          "ETH": "ethereum",
          "BNB": "binancecoin",
          "SOL": "solana",
          "USDT": "tether",
          "USDC": "usd-coin",
      }
      
      def get_prices(self, symbols: list[str]) -> dict:
          """Получить текущие цены в USD"""
          ids = [self.SYMBOL_TO_ID[s] for s in symbols if s in self.SYMBOL_TO_ID]
          ids_str = ",".join(ids)
          
          response = requests.get(
              f"{self.COINGECKO_URL}/simple/price",
              params={"ids": ids_str, "vs_currencies": "usd"}
          )
          
          data = response.json()
          result = {}
          for symbol, coin_id in self.SYMBOL_TO_ID.items():
              if coin_id in data:
                  result[symbol] = data[coin_id]["usd"]
          return result
  ```

- [ ] **2.2** Эндпоинт расчёта стоимости портфеля
  ```python
  # portfolios/views.py
  class PortfolioValueView(APIView):
      def get(self, request):
          portfolio = Portfolio.objects.filter(user=request.user, is_active=True).first()
          if not portfolio:
              return Response({"error": "Portfolio not found"}, status=404)
          
          assets = portfolio.portfolioasset_set.all()
          symbols = [a.symbol for a in assets]
          
          price_service = PriceService()
          prices = price_service.get_prices(symbols)
          
          total_value = 0
          assets_data = []
          
          for asset in assets:
              # Расчёт: initial_amount * (percentage/100) * (current_price/initial_price)
              # Для MVP упрощаем: показываем распределение по текущим ценам
              asset_value = float(portfolio.initial_amount) * float(asset.percentage) / 100
              assets_data.append({
                  "symbol": asset.symbol,
                  "percentage": float(asset.percentage),
                  "value": asset_value,
                  "current_price": prices.get(asset.symbol, 0)
              })
              total_value += asset_value
          
          return Response({
              "total_value": total_value,
              "initial_value": float(portfolio.initial_amount),
              "profit_loss": 0,  # Упрощение для MVP
              "profit_loss_percent": 0,
              "assets": assets_data,
              "start_date": portfolio.start_date,
          })
  ```

---

### Этап 3: Сервис ИИ-консультанта

**Задачи:**

- [ ] **3.1** Создать `AIAdvisorService`
  ```python
  # advisor/services.py
  from openai import OpenAI
  from django.conf import settings

  class AIAdvisorService:
      def __init__(self):
          self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
      
      def get_system_prompt(self, profile, portfolio):
          experience_detail = {
              "beginner": "кратко и просто",
              "some": "с базовыми пояснениями",
              "medium": "подробно",
              "advanced": "детально с техническими терминами"
          }
          
          return f"""Ты — крипто-консультант для долгосрочных инвесторов.
  
  Профиль инвестора:
  - Горизонт инвестирования: {profile.investment_horizon} лет
  - Сумма инвестиций: ${profile.investment_amount}
  - Допустимая просадка: {profile.max_drawdown}%
  - Уровень опыта: {profile.experience_level}
  
  Стиль ответа: {experience_detail.get(profile.experience_level, 'понятно')}
  
  Состав портфеля:
  {self._format_portfolio(portfolio)}
  
  Правила:
  1. Давай рекомендации для ДОЛГОСРОЧНОЙ стратегии (не дейтрейдинг)
  2. При просадке больше {profile.max_drawdown}% предупреждай о рисках
  3. Не давай финансовых советов — только информационная поддержка
  4. Отвечай на русском языке
  """
      
      def _format_portfolio(self, portfolio):
          assets = portfolio.portfolioasset_set.all()
          lines = []
          for asset in assets:
              lines.append(f"- {asset.symbol}: {asset.percentage}%")
          return "\n".join(lines)
      
      def get_recommendation(self, user, message: str) -> str:
          profile = user.investorprofile
          portfolio = Portfolio.objects.filter(user=user, is_active=True).first()
          
          system_prompt = self.get_system_prompt(profile, portfolio)
          
          # Получаем историю (последние 10 сообщений)
          history = ChatMessage.objects.filter(user=user).order_by('-created_at')[:10]
          messages = [{"role": "system", "content": system_prompt}]
          
          for msg in reversed(history):
              messages.append({"role": msg.role, "content": msg.content})
          
          messages.append({"role": "user", "content": message})
          
          response = self.client.chat.completions.create(
              model="gpt-4o-mini",  # или gpt-4o для лучшего качества
              messages=messages,
              max_tokens=1000,
              temperature=0.7
          )
          
          return response.choices[0].message.content
  ```

- [ ] **3.2** Эндпоинт чата
  ```python
  # advisor/views.py
  class ChatView(APIView):
      def post(self, request):
          message = request.data.get("message")
          if not message:
              return Response({"error": "Message required"}, status=400)
          
          # Сохраняем сообщение пользователя
          ChatMessage.objects.create(
              user=request.user,
              role="user",
              content=message
          )
          
          # Получаем ответ ИИ
          advisor = AIAdvisorService()
          response_text = advisor.get_recommendation(request.user, message)
          
          # Сохраняем ответ
          ChatMessage.objects.create(
              user=request.user,
              role="assistant",
              content=response_text
          )
          
          return Response({"response": response_text})
  ```

---

### Этап 4: Frontend — базовый интерфейс

**Задачи:**

- [ ] **4.1** Создать Next.js проект
  ```powershell
  npx create-next-app@latest frontend --typescript --tailwind --app
  cd frontend
  npm install axios zustand
  ```

- [ ] **4.2** Структура страниц
  ```
  frontend/src/app/
  ├── page.tsx              # Главная (редирект)
  ├── login/page.tsx        # Вход
  ├── register/page.tsx     # Регистрация
  ├── questionnaire/page.tsx # Анкета (10 вопросов)
  ├── dashboard/page.tsx    # Дашборд с портфелем
  └── chat/page.tsx         # Чат с консультантом
  ```

- [ ] **4.3** Страница анкеты `/questionnaire`
  - Пошаговый визард (10 шагов)
  - Прогресс-бар
  - Валидация на каждом шаге
  - Комментарии сервиса после ответа

- [ ] **4.4** Страница дашборда `/dashboard`
  - Общая стоимость портфеля
  - Распределение активов (простая таблица или pie chart)
  - Ссылка на чат с консультантом

- [ ] **4.5** Страница чата `/chat`
  - Список сообщений
  - Поле ввода
  - Кнопка отправки
  - Индикатор загрузки

**Компоненты:**
```
frontend/src/components/
├── auth/
│   ├── LoginForm.tsx
│   └── RegisterForm.tsx
├── questionnaire/
│   ├── QuestionStep.tsx
│   ├── SliderInput.tsx
│   ├── RadioGroup.tsx
│   └── ProgressBar.tsx
├── dashboard/
│   ├── PortfolioSummary.tsx
│   └── AssetList.tsx
└── chat/
    ├── ChatMessages.tsx
    └── ChatInput.tsx
```

---

## 🗂 Итоговая структура проекта

```
CryptoConsult/
├── backend/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── users/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── portfolios/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services.py
│   ├── advisor/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services.py
│   ├── manage.py
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── services/
│   ├── package.json
│   └── .env.local
├── PROJECT.md
├── PLAN.md
├── PLAN01.md
└── README.md
```

---

## ⚡ Быстрый старт

### Backend

```powershell
# Создать и активировать виртуальное окружение
cd backend
python -m venv venv
.\venv\Scripts\Activate

# Установить зависимости
pip install -r requirements.txt

# Создать .env файл
echo "OPENAI_API_KEY=sk-your-key-here" > .env
echo "SECRET_KEY=your-django-secret-key" >> .env

# Миграции
python manage.py makemigrations
python manage.py migrate

# Запуск
python manage.py runserver
```

### Frontend

```powershell
cd frontend

# Установить зависимости
npm install

# Создать .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local

# Запуск
npm run dev
```

---

## ✅ Критерии готовности минимального MVP

| Функция | Статус |
|---------|--------|
| Регистрация пользователя | 🔲 |
| Авторизация (JWT) | 🔲 |
| Анкета инвестора (10 вопросов) | 🔲 |
| Создание портфеля | 🔲 |
| Отображение портфеля на дашборде | 🔲 |
| Получение цен криптовалют | 🔲 |
| Чат с ИИ-консультантом | 🔲 |
| Адаптация ответов по уровню опыта | 🔲 |

**MVP готов когда:**
- ✅ Пользователь может зарегистрироваться и войти
- ✅ Пользователь проходит анкету из 10 вопросов
- ✅ Создаётся портфель с базовым распределением (BTC 50%, ETH 25%, ...)
- ✅ На дашборде видна стоимость портфеля
- ✅ Можно задать вопрос ИИ и получить рекомендацию
- ✅ ИИ учитывает профиль инвестора в ответах

---

## 🚀 Следующие шаги после MVP

После валидации концепции перейти к [PLAN.md](./PLAN.md) для полной реализации:
- Добавить Redis для кэширования цен
- Добавить Celery для фоновых задач
- Реализовать систему уведомлений
- Добавить графики динамики портфеля
- Развернуть в Docker

---

*План создан: 25.01.2026*
