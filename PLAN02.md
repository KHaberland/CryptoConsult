# PLAN02: Удаление регистрации/авторизации из MVP

## Цель

Упростить MVP, убрав обязательную регистрацию и авторизацию. Пользователь сразу начинает работать с сервисом, данные сохраняются по `session_id` в localStorage и на backend.

---

## Текущее состояние

```
Пользователь → Регистрация → Логин → Анкета → Dashboard → Чат
```

## Целевое состояние

```
Пользователь → Анкета → Dashboard → Чат
```

---

## Этап 1: Backend — настройки и middleware

### 1.1 Изменить `config/settings.py`

**Файл:** `backend/config/settings.py`

**Изменения:**
```python
# Было:
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

# Стало:
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
}
```

**Удалить из INSTALLED_APPS:**
- `'rest_framework_simplejwt'`

**Удалить настройки:**
- `SIMPLE_JWT`

### 1.2 Создать middleware для session_id

**Создать файл:** `backend/config/middleware.py`

```python
import uuid

class SessionMiddleware:
    """
    Middleware для генерации и проверки session_id.
    Session ID передаётся в заголовке X-Session-ID.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Получаем session_id из заголовка
        session_id = request.headers.get('X-Session-ID')
        
        # Если нет — генерируем новый
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Сохраняем в request для использования в views
        request.session_id = session_id
        
        response = self.get_response(request)
        
        # Возвращаем session_id в заголовке ответа
        response['X-Session-ID'] = session_id
        
        return response
```

**Добавить в `settings.py` MIDDLEWARE:**
```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'config.middleware.SessionMiddleware',  # Добавить
    # ... остальные
]
```

---

## Этап 2: Backend — изменение моделей

### 2.1 Изменить `users/models.py`

**Изменения в `InvestorProfile`:**

```python
class InvestorProfile(models.Model):
    # Убрать обязательную связь с User
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='investor_profile',
        null=True,      # Добавить
        blank=True      # Добавить
    )
    
    # Добавить session_id
    session_id = models.CharField(
        max_length=36,
        unique=True,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    # ... остальные поля без изменений
```

### 2.2 Изменить `portfolios/models.py`

**Изменения в `Portfolio`:**

```python
class Portfolio(models.Model):
    # Убрать обязательную связь с User
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='portfolios',
        null=True,      # Добавить
        blank=True      # Добавить
    )
    
    # Добавить session_id
    session_id = models.CharField(
        max_length=36,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    # ... остальные поля без изменений
```

### 2.3 Изменить `advisor/models.py`

**Изменения в `ChatMessage`:**

```python
class ChatMessage(models.Model):
    # Убрать обязательную связь с User
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,      # Добавить
        blank=True      # Добавить
    )
    
    # Добавить session_id
    session_id = models.CharField(
        max_length=36,
        db_index=True,
        verbose_name='ID сессии'
    )
    
    # ... остальные поля без изменений
```

### 2.4 Создать миграции

```powershell
cd backend
.\venv\Scripts\python manage.py makemigrations
.\venv\Scripts\python manage.py migrate
```

---

## Этап 3: Backend — изменение Views

### 3.1 Изменить `users/views.py`

**Удалить:**
- `RegisterView`
- `UserMeView`

**Изменить `InvestorProfileView`:**

```python
class InvestorProfileView(APIView):
    permission_classes = (AllowAny,)
    
    def get(self, request):
        session_id = request.session_id
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
            serializer = InvestorProfileSerializer(profile)
            return Response(serializer.data)
        except InvestorProfile.DoesNotExist:
            return Response(
                {'detail': 'Профиль не найден. Заполните анкету.'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request):
        session_id = request.session_id
        
        # Проверяем, есть ли уже профиль
        if InvestorProfile.objects.filter(session_id=session_id).exists():
            return Response(
                {'detail': 'Профиль уже существует.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = InvestorProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(session_id=session_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        session_id = request.session_id
        try:
            profile = InvestorProfile.objects.get(session_id=session_id)
        except InvestorProfile.DoesNotExist:
            return Response(
                {'detail': 'Профиль не найден.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = InvestorProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

### 3.2 Изменить `users/urls.py`

```python
from django.urls import path
from .views import InvestorProfileView

urlpatterns = [
    # Убрать register, login, refresh, me
    # Оставить только profile
]
```

**Изменить `users/profile_urls.py`:**
```python
urlpatterns = [
    path('', InvestorProfileView.as_view(), name='investor_profile'),
]
```

### 3.3 Изменить `portfolios/views.py`

**Заменить `request.user` на `request.session_id`:**

```python
class PortfolioListCreateView(APIView):
    permission_classes = (AllowAny,)
    
    def get(self, request):
        portfolios = Portfolio.objects.filter(session_id=request.session_id)
        # ...
    
    def post(self, request):
        # Проверяем активный портфель по session_id
        active = Portfolio.objects.filter(
            session_id=request.session_id,
            is_active=True
        ).first()
        # ...
        serializer.save(session_id=request.session_id)
```

**Аналогично для:**
- `PortfolioDetailView`
- `PortfolioValueView`
- `ActivePortfolioView`

### 3.4 Изменить `advisor/views.py`

**Заменить `request.user` на `request.session_id`:**

```python
class ChatView(APIView):
    permission_classes = (AllowAny,)
    
    def post(self, request):
        session_id = request.session_id
        
        # Получаем портфель по session_id
        portfolio = Portfolio.objects.filter(
            session_id=session_id,
            is_active=True
        ).first()
        
        # Сохраняем сообщение с session_id
        user_message = ChatMessage.objects.create(
            session_id=session_id,
            role='user',
            content=message,
            portfolio=portfolio
        )
        # ...
```

**Аналогично для:**
- `ChatHistoryView`
- `PortfolioSummaryView`
- `RiskAnalysisView`
- `DrawdownAlertView`

### 3.5 Изменить `advisor/services.py`

**В `AIAdvisorService`:**

Заменить методы, принимающие `user`, на методы, принимающие `session_id`:

```python
def get_system_prompt(self, session_id: str) -> str:
    # Получаем профиль по session_id
    try:
        profile = InvestorProfile.objects.get(session_id=session_id)
    except InvestorProfile.DoesNotExist:
        profile = None
    
    # Получаем портфель по session_id
    portfolio = Portfolio.objects.filter(
        session_id=session_id,
        is_active=True
    ).first()
    # ...

def get_recommendation(self, session_id: str, message: str) -> str:
    # ...

def analyze_risk(self, session_id: str) -> Dict:
    # ...

def get_drawdown_alert(self, session_id: str) -> Optional[Dict]:
    # ...
```

### 3.6 Изменить `config/urls.py`

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    # Убрать path('api/auth/', ...)
    path('api/profile/', include('users.profile_urls')),
    path('api/portfolio/', include('portfolios.urls')),
    path('api/chat/', include('advisor.urls')),
]
```

---

## Этап 4: Frontend — удаление авторизации

### 4.1 Удалить файлы

```
frontend/src/app/login/page.tsx      — удалить
frontend/src/app/register/page.tsx   — удалить
frontend/src/store/authStore.ts      — удалить
```

### 4.2 Создать `sessionStore.ts`

**Файл:** `frontend/src/store/sessionStore.ts`

```typescript
import { create } from 'zustand'

interface SessionState {
  sessionId: string | null
  isReady: boolean
  
  initSession: () => void
  getSessionId: () => string
}

const generateSessionId = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessionId: null,
  isReady: false,
  
  initSession: () => {
    if (typeof window === 'undefined') return
    
    let sessionId = localStorage.getItem('session_id')
    
    if (!sessionId) {
      sessionId = generateSessionId()
      localStorage.setItem('session_id', sessionId)
    }
    
    set({ sessionId, isReady: true })
  },
  
  getSessionId: () => {
    const state = get()
    if (state.sessionId) return state.sessionId
    
    if (typeof window !== 'undefined') {
      let sessionId = localStorage.getItem('session_id')
      if (!sessionId) {
        sessionId = generateSessionId()
        localStorage.setItem('session_id', sessionId)
      }
      return sessionId
    }
    
    return ''
  },
}))
```

### 4.3 Изменить `services/api.ts`

**Убрать:**
- JWT интерцепторы
- `authApi`

**Добавить:**
```typescript
import { useSessionStore } from '@/store/sessionStore'

// Интерцептор для добавления session_id
api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      let sessionId = localStorage.getItem('session_id')
      if (!sessionId) {
        sessionId = generateSessionId()
        localStorage.setItem('session_id', sessionId)
      }
      config.headers['X-Session-ID'] = sessionId
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Убрать интерцептор для refresh токена
```

### 4.4 Изменить `app/page.tsx`

```typescript
'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSessionStore } from '@/store/sessionStore'
import { profileApi } from '@/services/api'

export default function Home() {
  const router = useRouter()
  const { initSession, isReady } = useSessionStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    initSession()
  }, [initSession])

  useEffect(() => {
    if (!isReady) return

    const checkProfile = async () => {
      try {
        await profileApi.get()
        // Профиль есть — идём на dashboard
        router.push('/dashboard')
      } catch (error: any) {
        if (error.response?.status === 404) {
          // Профиля нет — идём на анкету
          router.push('/questionnaire')
        }
      } finally {
        setChecking(false)
      }
    }

    checkProfile()
  }, [isReady, router])

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Загрузка...</p>
      </div>
    </main>
  )
}
```

### 4.5 Изменить `components/layout/Header.tsx`

**Убрать:**
- Email пользователя
- Кнопку "Выйти"
- `useAuthStore`

```typescript
export function Header() {
  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link href="/dashboard" className="flex items-center">
            <span className="text-xl font-bold text-primary-600">
              Крипто-Консультант
            </span>
          </Link>
          
          <nav className="flex items-center space-x-4">
            <Link href="/dashboard" className="...">
              <LayoutDashboard className="w-5 h-5 mr-1" />
              <span>Дашборд</span>
            </Link>
            
            <Link href="/chat" className="...">
              <MessageCircle className="w-5 h-5 mr-1" />
              <span>Консультант</span>
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
```

### 4.6 Изменить остальные страницы

**`app/questionnaire/page.tsx`:**
- Убрать `useAuthStore`
- Убрать проверку `isAuthenticated`
- Использовать `useSessionStore`

**`app/dashboard/page.tsx`:**
- Убрать `useAuthStore`
- Убрать проверку `isAuthenticated`
- Редирект на `/questionnaire` если нет профиля

**`app/chat/page.tsx`:**
- Убрать `useAuthStore`
- Убрать проверку `isAuthenticated`

### 4.7 Изменить `portfolioStore.ts`

**Убрать зависимость от авторизации:**
- Убрать проверки `isAuthenticated`
- Использовать `sessionStore` для инициализации

---

## Этап 5: Тестирование

### 5.1 Проверить сценарии

1. **Новый пользователь:**
   - Открывает сайт → видит анкету
   - Заполняет анкету → создаётся портфель
   - Переходит на dashboard → видит портфель
   - Открывает чат → работает

2. **Возврат пользователя:**
   - Открывает сайт → сразу dashboard
   - Данные сохранены

3. **Другой браузер:**
   - Новая сессия, новый профиль

### 5.2 Проверить API

```powershell
# Создать профиль
curl -X POST http://localhost:8000/api/profile/ `
  -H "Content-Type: application/json" `
  -H "X-Session-ID: test-session-123" `
  -d '{"investment_horizon": 3, "investment_amount": 10000, ...}'

# Получить профиль
curl http://localhost:8000/api/profile/ `
  -H "X-Session-ID: test-session-123"
```

---

## Файлы для изменения

### Backend (9 файлов)

| Файл | Действие |
|------|----------|
| `config/settings.py` | Изменить |
| `config/middleware.py` | Создать |
| `config/urls.py` | Изменить |
| `users/models.py` | Изменить |
| `users/views.py` | Изменить |
| `users/urls.py` | Изменить |
| `portfolios/models.py` | Изменить |
| `portfolios/views.py` | Изменить |
| `advisor/models.py` | Изменить |
| `advisor/views.py` | Изменить |
| `advisor/services.py` | Изменить |

### Frontend (8 файлов)

| Файл | Действие |
|------|----------|
| `app/login/page.tsx` | Удалить |
| `app/register/page.tsx` | Удалить |
| `store/authStore.ts` | Удалить |
| `store/sessionStore.ts` | Создать |
| `services/api.ts` | Изменить |
| `app/page.tsx` | Изменить |
| `app/questionnaire/page.tsx` | Изменить |
| `app/dashboard/page.tsx` | Изменить |
| `app/chat/page.tsx` | Изменить |
| `components/layout/Header.tsx` | Изменить |

---

## Порядок выполнения

1. **Backend: Middleware и settings** (~15 мин)
2. **Backend: Модели и миграции** (~20 мин)
3. **Backend: Views** (~30 мин)
4. **Frontend: sessionStore и api** (~15 мин)
5. **Frontend: Страницы** (~30 мин)
6. **Тестирование** (~20 мин)

**Общее время:** ~2 часа

---

## Откат (при необходимости)

Если нужно вернуть авторизацию:
1. Git revert изменений
2. Или добавить флаг `REQUIRE_AUTH` в settings
3. Данные с `session_id` можно мигрировать в аккаунты
