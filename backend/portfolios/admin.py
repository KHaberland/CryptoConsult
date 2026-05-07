from django.contrib import admin
from .models import (
    Portfolio,
    PortfolioAsset,
    PortfolioContribution,
    PortfolioContributionItem,
    PortfolioWithdrawal,
    PortfolioSwap,
    Wallet,
    WalletHolding,
    WalletTransfer,
    HoldingAdjustment,
)


class PortfolioAssetInline(admin.TabularInline):
    model = PortfolioAsset
    extra = 1


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'user',
        'initial_amount',
        'target_years',
        'is_active',
        'start_date'
    )
    list_filter = ('is_active', 'target_years')
    search_fields = ('user__email', 'name')
    inlines = [PortfolioAssetInline]


@admin.register(PortfolioAsset)
class PortfolioAssetAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'portfolio', 'percentage', 'initial_price')
    list_filter = ('symbol',)
    search_fields = ('portfolio__user__email', 'symbol')


class PortfolioContributionItemInline(admin.TabularInline):
    model = PortfolioContributionItem
    extra = 0
    readonly_fields = ('symbol', 'units', 'purchase_price', 'value_usd')


@admin.register(PortfolioContribution)
class PortfolioContributionAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'amount', 'contributed_at')
    list_filter = ('contributed_at',)
    search_fields = ('portfolio__name',)
    inlines = [PortfolioContributionItemInline]


@admin.register(PortfolioWithdrawal)
class PortfolioWithdrawalAdmin(admin.ModelAdmin):
    list_display = ('portfolio', 'amount', 'withdrawn_at', 'value_after')
    list_filter = ('withdrawn_at',)
    search_fields = ('portfolio__name',)


@admin.register(PortfolioSwap)
class PortfolioSwapAdmin(admin.ModelAdmin):
    list_display = (
        'portfolio',
        'from_symbol',
        'from_units',
        'to_symbol',
        'to_units',
        'fee_usd',
        'swapped_at',
    )
    list_filter = ('swapped_at', 'from_symbol', 'to_symbol')
    search_fields = ('portfolio__name', 'from_symbol', 'to_symbol')


class WalletHoldingInline(admin.TabularInline):
    model = WalletHolding
    extra = 0
    readonly_fields = ('updated_at',)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('name', 'portfolio', 'type', 'is_default', 'created_at')
    list_filter = ('type', 'is_default')
    search_fields = ('name', 'portfolio__name')
    inlines = [WalletHoldingInline]


@admin.register(WalletHolding)
class WalletHoldingAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'wallet', 'units', 'updated_at')
    list_filter = ('symbol',)
    search_fields = ('symbol', 'wallet__name', 'wallet__portfolio__name')


@admin.register(WalletTransfer)
class WalletTransferAdmin(admin.ModelAdmin):
    list_display = (
        'portfolio',
        'symbol',
        'from_wallet',
        'to_wallet',
        'from_units',
        'to_units',
        'fee_units',
        'fee_usd',
        'occurred_on',
    )
    list_filter = ('occurred_on', 'symbol')
    search_fields = ('portfolio__name', 'symbol', 'from_wallet__name', 'to_wallet__name')


@admin.register(HoldingAdjustment)
class HoldingAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'holding',
        'units_before',
        'units_after',
        'delta',
        'value_delta_usd',
        'reason',
        'occurred_on',
    )
    list_filter = ('reason', 'occurred_on')
    search_fields = (
        'holding__symbol',
        'holding__wallet__name',
        'holding__wallet__portfolio__name',
        'note',
    )
