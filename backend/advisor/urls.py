from django.urls import path
from .views import (
    ChatView,
    ChatHistoryView,
    PortfolioSummaryView,
    RiskAnalysisView,
    DrawdownAlertView,
    QuickCommandsView,
)

urlpatterns = [
    # Основной чат
    path('', ChatView.as_view(), name='chat'),
    path('history/', ChatHistoryView.as_view(), name='chat_history'),
    
    # Аналитика
    path('summary/', PortfolioSummaryView.as_view(), name='portfolio_summary'),
    path('risk/', RiskAnalysisView.as_view(), name='risk_analysis'),
    path('alert/', DrawdownAlertView.as_view(), name='drawdown_alert'),
    
    # Справка
    path('commands/', QuickCommandsView.as_view(), name='quick_commands'),
]
