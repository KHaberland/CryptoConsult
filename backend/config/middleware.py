"""
Middleware для работы с session_id и CORS.
"""

import uuid
import logging

logger = logging.getLogger(__name__)


class EnsureCorsMiddleware:
    """
    Добавляет CORS-заголовки к любому ответу, у которого их ещё нет.
    Нужно, чтобы при 500 и других ошибках браузер получал CORS и не скрывал текст ошибки.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        origin = request.headers.get('Origin')
        if origin and not response.get('Access-Control-Allow-Origin'):
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            if request.method == 'OPTIONS':
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Session-ID'
        return response


class SessionIdMiddleware:
    """
    Middleware для генерации и проверки session_id.
    Session ID передаётся в заголовке X-Session-ID.
    
    Если заголовок отсутствует — генерируется новый session_id.
    Session ID всегда возвращается в заголовке ответа.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Получаем session_id из заголовка запроса
        session_id = request.headers.get('X-Session-ID')
        
        # Валидируем формат UUID
        if session_id:
            try:
                # Проверяем, что это валидный UUID
                uuid.UUID(session_id)
            except ValueError:
                # Если невалидный — генерируем новый
                session_id = str(uuid.uuid4())
        else:
            # Если заголовка нет — генерируем новый
            session_id = str(uuid.uuid4())
        
        # Сохраняем session_id в объекте request для использования в views
        request.session_id = session_id
        
        # Обрабатываем запрос
        response = self.get_response(request)
        
        # Добавляем session_id в заголовок ответа
        response['X-Session-ID'] = session_id
        
        return response
