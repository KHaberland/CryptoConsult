"""
Проверка FRED API и макро-данных.
Запуск: python manage.py check_fred
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Проверка FRED_API_KEY и получение макро-данных"

    def handle(self, *args, **options):
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            self.stderr.write(
                self.style.ERROR(
                    "FRED_API_KEY не найден в окружении!\n"
                    "Добавьте в .env (в корне проекта или в backend/):\n"
                    "  FRED_API_KEY=ваш-ключ\n\n"
                    "Бесплатный ключ: https://fred.stlouisfed.org/docs/api/api_key.html"
                )
            )
            return

        self.stdout.write(f"FRED_API_KEY: {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****'}")
        self.stdout.write("")

        try:
            from market_data import get_macro_data

            macro = get_macro_data(btc_prices=None)
            if not macro:
                self.stderr.write(self.style.ERROR("get_macro_data вернул None"))
                return

            has_data = any(
                macro.get(k) is not None
                for k in ("fed_funds_rate", "treasury_10y", "dxy", "sp500")
            )
            if not has_data:
                self.stderr.write(
                    self.style.ERROR(
                        "Ключ задан, но FRED API не вернул данных. "
                        "Проверьте: 1) ключ валиден на fred.stlouisfed.org, "
                        "2) логи Django (WARNING) на ошибки."
                    )
                )
                return

            self.stdout.write(self.style.SUCCESS("Макро-данные получены:"))
            for k, v in macro.items():
                if k != "interpretation" and v is not None:
                    self.stdout.write(f"  {k}: {v}")
            self.stdout.write(f"  interpretation: {macro.get('interpretation', '')}")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ошибка: {e}"))
