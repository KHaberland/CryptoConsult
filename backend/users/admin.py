from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, InvestorProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'is_staff', 'date_joined')
    search_fields = ('email', 'username')
    ordering = ('-date_joined',)


@admin.register(InvestorProfile)
class InvestorProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'investment_horizon',
        'investment_amount',
        'max_drawdown',
        'experience_level',
        'created_at'
    )
    list_filter = ('experience_level', 'use_dca', 'needs_liquidity')
    search_fields = ('user__email',)
