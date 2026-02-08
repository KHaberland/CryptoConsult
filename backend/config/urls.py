"""
URL configuration for CryptoConsult project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # api/auth/ удалён — авторизация не используется
    path('api/profile/', include('users.profile_urls')),
    path('api/portfolio/', include('portfolios.urls')),
    path('api/chat/', include('advisor.urls')),
]
