"""List user names from User and InvestorProfile."""
import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User, InvestorProfile

print('=== User (registered) ===')
users = User.objects.all().order_by('date_joined')
print(f'Total: {users.count()}')
for u in users:
    print(f'  email: {u.email}, username: {u.username}')

print()
print('=== InvestorProfile (MVP names) ===')
profiles = InvestorProfile.objects.all().order_by('created_at')
print(f'Total profiles: {profiles.count()}')
for p in profiles:
    name = p.name or '(empty)'
    sess = p.session_id[:8] + '...' if len(p.session_id) > 8 else p.session_id
    dt = p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else '-'
    print(f'  name: {name}, session_id: {sess}, created: {dt}')
