"""
WSGI config for CryptoConsult project.
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Логируем версию при старте
logger = logging.getLogger(__name__)
try:
    from django.conf import settings
    logger.info("CryptoConsult API v%s запущен", getattr(settings, 'APP_VERSION', '?'))
except Exception:
    pass
