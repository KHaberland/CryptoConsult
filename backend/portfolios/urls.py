from django.urls import path
from .views import (
    # Portfolio views
    PortfolioListCreateView,
    PortfolioDetailView,
    PortfolioValueView,
    ActivePortfolioView,
    ContributePortfolioView,
    WithdrawProposalView,
    WithdrawPortfolioView,
    RebalancePortfolioView,
    # Price views
    PricesView,
    PricesWithChangesView,
    MarketDataView,
    HistoricalPricesView,
    SupportedAssetsView,
)

urlpatterns = [
    # Portfolio endpoints
    path('', PortfolioListCreateView.as_view(), name='portfolio_list_create'),
    path('active/', ActivePortfolioView.as_view(), name='portfolio_active'),
    path('value/', PortfolioValueView.as_view(), name='portfolio_value'),
    path('contribute/', ContributePortfolioView.as_view(), name='portfolio_contribute'),
    path('withdraw/proposal/', WithdrawProposalView.as_view(), name='portfolio_withdraw_proposal'),
    path('withdraw/', WithdrawPortfolioView.as_view(), name='portfolio_withdraw'),
    path('rebalance/', RebalancePortfolioView.as_view(), name='portfolio_rebalance'),
    path('<int:pk>/', PortfolioDetailView.as_view(), name='portfolio_detail'),
    
    # Price endpoints
    path('prices/', PricesView.as_view(), name='prices'),
    path('prices/changes/', PricesWithChangesView.as_view(), name='prices_changes'),
    path('prices/market/', MarketDataView.as_view(), name='market_data'),
    path('prices/history/<str:symbol>/', HistoricalPricesView.as_view(), name='historical_prices'),
    path('prices/supported/', SupportedAssetsView.as_view(), name='supported_assets'),
]
