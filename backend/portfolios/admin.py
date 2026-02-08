from django.contrib import admin
from .models import Portfolio, PortfolioAsset


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
