# CryptoConsult Frontend

Next.js приложение для сервиса Крипто-Консультант.

## Требования

- Node.js 18+
- npm или yarn

## Быстрый старт

### 1. Установить зависимости

```powershell
cd frontend
npm install
```

### 2. Настроить переменные окружения

Скопируйте `.env.example` в `.env.local`:

```powershell
copy .env.example .env.local
```

Отредактируйте `.env.local` при необходимости:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### 3. Запустить сервер разработки

```powershell
npm run dev
```

Приложение будет доступно по адресу: http://localhost:3000

## Структура проекта

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── login/             # Страница входа
│   │   ├── register/          # Страница регистрации
│   │   ├── questionnaire/     # Анкета инвестора
│   │   ├── dashboard/         # Дашборд портфеля
│   │   ├── chat/              # Чат с консультантом
│   │   ├── layout.tsx         # Корневой layout
│   │   ├── page.tsx           # Главная страница
│   │   └── globals.css        # Глобальные стили
│   ├── components/
│   │   ├── ui/                # UI компоненты
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Alert.tsx
│   │   │   ├── Progress.tsx
│   │   │   └── Slider.tsx
│   │   └── layout/            # Layout компоненты
│   │       └── Header.tsx
│   ├── services/
│   │   └── api.ts             # API клиент и методы
│   ├── store/
│   │   ├── authStore.ts       # Состояние авторизации
│   │   ├── portfolioStore.ts  # Состояние портфеля
│   │   └── chatStore.ts       # Состояние чата
│   └── lib/
│       └── utils.ts           # Утилиты
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── next.config.js
```

## Страницы

| Путь | Описание |
|------|----------|
| `/` | Редирект на dashboard или login |
| `/login` | Вход в систему |
| `/register` | Регистрация |
| `/questionnaire` | Анкета инвестора (10 вопросов) |
| `/dashboard` | Дашборд с портфелем |
| `/chat` | Чат с ИИ-консультантом |

## Технологии

- **Next.js 14** — React фреймворк
- **TypeScript** — типизация
- **Tailwind CSS** — стилизация
- **Zustand** — управление состоянием
- **Axios** — HTTP клиент
- **Lucide React** — иконки

## Команды

```powershell
# Разработка
npm run dev

# Сборка
npm run build

# Запуск production
npm start

# Линтер
npm run lint
```

## API Интеграция

Все API запросы настроены в `src/services/api.ts`:

- `authApi` — авторизация и регистрация
- `profileApi` — профиль инвестора
- `portfolioApi` — управление портфелем
- `pricesApi` — данные о ценах
- `chatApi` — чат с консультантом

## Функционал

### Авторизация
- JWT аутентификация
- Автоматическое обновление токенов
- Защита маршрутов

### Анкета инвестора
- Пошаговый wizard (10 вопросов)
- Слайдеры и выбор вариантов
- Автоматическое создание портфеля

### Дашборд
- Отображение стоимости портфеля
- Прибыль/убыток в реальном времени
- Таблица активов с 24ч изменениями
- Прогресс до целевой даты

### Чат с консультантом
- Быстрые команды (/status, /risk и др.)
- История сообщений
- Алерты о просадке
- Очистка истории
