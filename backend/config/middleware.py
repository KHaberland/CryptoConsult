"""
Middleware для работы с session_id.
Позволяет идентифицировать пользователей без регистрации.
"""

import uuid


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
