"""Delete InvestorProfile and related data by name."""
import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import InvestorProfile
from portfolios.models import Portfolio

NAMES = ['user01', 'user02', 'user03', 'user04', 'user05', 'user06', 'user07']

profiles = InvestorProfile.objects.filter(name__in=NAMES)
count = profiles.count()
if count == 0:
    print('No matching profiles found.')
    sys.exit(0)

session_ids = list(profiles.values_list('session_id', flat=True))
portfolios_deleted = Portfolio.objects.filter(session_id__in=session_ids).delete()
profiles_deleted = profiles.delete()

print(f'Deleted {portfolios_deleted[0]} portfolio(s) and related data')
print(f'Deleted {profiles_deleted[0]} InvestorProfile(s): {", ".join(NAMES)}')
