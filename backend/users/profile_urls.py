from django.urls import path
from .views import InvestorProfileView, ProfileLookupView

urlpatterns = [
    path('', InvestorProfileView.as_view(), name='investor_profile'),
    path('lookup/', ProfileLookupView.as_view(), name='profile_lookup'),
]
