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
    Top10RecommendedView,
    PortfolioImportView,
    SwapQuoteView,
    SwapExecuteView,
    TradableAssetsView,
    WalletListCreateView,
    WalletDetailView,
    WalletTransferView,
    HoldingAdjustView,
    # FiatCashFlow (PLAN11)
    FiatCashFlowListCreateView,
    FiatCashFlowDetailView,
    PortfolioBaseCurrencyView,
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
    path('swap/quote/', SwapQuoteView.as_view(), name='portfolio_swap_quote'),
    path('swap/', SwapExecuteView.as_view(), name='portfolio_swap'),
    path('tradable-assets/', TradableAssetsView.as_view(), name='portfolio_tradable_assets'),
    path('wallets/', WalletListCreateView.as_view(), name='wallet_list_create'),
    path('wallets/transfer/', WalletTransferView.as_view(), name='wallet_transfer'),
    path(
        'wallets/<int:wallet_id>/holdings/<str:symbol>/adjust/',
        HoldingAdjustView.as_view(),
        name='wallet_holding_adjust',
    ),
    path('wallets/<int:pk>/', WalletDetailView.as_view(), name='wallet_detail'),
    path('cash-flows/', FiatCashFlowListCreateView.as_view(), name='fiat_cash_flow_list_create'),
    path('cash-flows/<int:pk>/', FiatCashFlowDetailView.as_view(), name='fiat_cash_flow_detail'),
    path('top10/', Top10RecommendedView.as_view(), name='portfolio_top10'),
    path('import/', PortfolioImportView.as_view(), name='portfolio_import'),
    path('<int:pk>/currency/', PortfolioBaseCurrencyView.as_view(), name='portfolio_base_currency'),
    path('<int:pk>/', PortfolioDetailView.as_view(), name='portfolio_detail'),
    
    # Price endpoints
    path('prices/', PricesView.as_view(), name='prices'),
    path('prices/changes/', PricesWithChangesView.as_view(), name='prices_changes'),
    path('prices/market/', MarketDataView.as_view(), name='market_data'),
    path('prices/history/<str:symbol>/', HistoricalPricesView.as_view(), name='historical_prices'),
    path('prices/supported/', SupportedAssetsView.as_view(), name='supported_assets'),
]
