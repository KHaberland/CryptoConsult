"""
URL configuration for CryptoConsult project.
"""

from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import path, include
from django.conf import settings


def favicon_view(request):
    """Отдаём пустой ответ на favicon.ico, чтобы браузер не получал 500."""
    return HttpResponse(status=204)


def root_view(request):
    """Корневая страница — API работает."""
    from django.conf import settings
    version = getattr(settings, 'APP_VERSION', '?')
    html = f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Крипто-Консультант API</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #f8fafc; color: #1e293b; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            h1 {{ color: #0284c7; margin-bottom: 1rem; }}
            .btn {{ display: inline-block; padding: 0.75rem 1.5rem; background: #0284c7; color: white; text-decoration: none; border-radius: 8px; font-weight: 500; margin: 1rem 0; }}
            .btn:hover {{ background: #0369a1; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin: 0.5rem 0; }}
            a {{ color: #0284c7; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Крипто-Консультант API</h1>
            <p>Версия: <strong>{version}</strong></p>
            <p>Это страница бэкенда. <strong>Приложение с интерфейсом</strong> запускается отдельно:</p>
            <a href="http://localhost:3000" class="btn">Открыть приложение (Frontend)</a>
            <p>Если порт 3000 занят, попробуйте <a href="http://localhost:3001">http://localhost:3001</a></p>
            <hr style="margin: 2rem 0; border: none; border-top: 1px solid #e2e8f0;">
            <p>API endpoints:</p>
            <ul>
                <li><a href="/api/version/">/api/version/</a></li>
                <li><a href="/api/profile/">/api/profile/</a></li>
                <li><a href="/api/portfolio/">/api/portfolio/</a></li>
                <li><a href="/api/chat/">/api/chat/</a></li>
                <li><a href="/admin/">/admin/</a></li>
            </ul>
        </div>
    </body>
    </html>
    '''
    return HttpResponse(html, content_type='text/html; charset=utf-8')


def version_view(request):
    """API: версия приложения и статус конфигурации."""
    api_key_configured = bool(getattr(settings, 'OPENAI_API_KEY', '') or getattr(settings, 'OPENROUTER_API_KEY', ''))
    return JsonResponse({
        'version': settings.APP_VERSION,
        'api_key_configured': api_key_configured,
    })


urlpatterns = [
    path('', root_view),
    path('api/version/', version_view),
    path('admin/', admin.site.urls),
    path('favicon.ico', favicon_view),
    # api/auth/ удалён — авторизация не используется
    path('api/profile/', include('users.profile_urls')),
    path('api/portfolio/', include('portfolios.urls')),
    path('api/chat/', include('advisor.urls')),
]
