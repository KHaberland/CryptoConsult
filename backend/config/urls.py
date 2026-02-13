"""
URL configuration for CryptoConsult project.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include


def favicon_view(request):
    """Отдаём пустой ответ на favicon.ico, чтобы браузер не получал 500."""
    return HttpResponse(status=204)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', favicon_view),
    # api/auth/ удалён — авторизация не используется
    path('api/profile/', include('users.profile_urls')),
    path('api/portfolio/', include('portfolios.urls')),
    path('api/chat/', include('advisor.urls')),
]
