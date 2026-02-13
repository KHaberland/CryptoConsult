"""List all registered users."""
import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User

users = User.objects.all().order_by('date_joined')
print(f"Total: {users.count()}\n")
print("email (login)          | username      | date_joined")
print("-" * 60)
for u in users:
    dt = u.date_joined.strftime("%Y-%m-%d %H:%M") if u.date_joined else "-"
    print(f"  {u.email:<22} | {(u.username or '-'):<13} | {dt}")
