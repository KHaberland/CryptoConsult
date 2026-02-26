#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Проверка работоспособности CryptoPanic API."""
import os
import sys
from pathlib import Path

# Загружаем .env: backend/.env и корень проекта
from dotenv import load_dotenv
_backend_env = Path(__file__).resolve().parent / ".env"
_root_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_root_env)
load_dotenv(_backend_env)  # backend перекрывает root

import requests

# Загружаем Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from market_data.institutions import _get_crypto_news, get_btc_institutions, CRYPTOPANIC_BASE

def main():
    api_key = os.environ.get("CRYPTOPANIC_API_KEY") or os.environ.get("CRYPTOPANIC_KEY")
    print("CRYPTOPANIC_API_KEY:", "SET" if api_key else "NOT SET")
    if not api_key:
        print("Add to backend/.env: CRYPTOPANIC_API_KEY=your_key_from_cryptopanic.com")
    print("CRYPTOPANIC_BASE:", CRYPTOPANIC_BASE)
    print("-" * 50)

    # Прямой запрос к API для диагностики
    if api_key:
        try:
            r = requests.get(
                f"{CRYPTOPANIC_BASE}/posts/",
                params={"auth_token": api_key, "filter": "hot", "currencies": "BTC"},
                timeout=10
            )
            print("Direct API request:")
            print("  HTTP status:", r.status_code)
            if not r.ok:
                print("  Response:", r.text[:300])
            else:
                data = r.json()
                results = data.get("results") or data.get("data") or []
                print("  Results count:", len(results) if isinstance(results, list) else "N/A")
                if isinstance(results, list) and results:
                    print("  First title:", (results[0].get("title") or "")[:60])
        except Exception as e:
            print("  Error:", e)
    else:
        # Тест без ключа — проверим, что endpoint отвечает
        try:
            r = requests.get(f"{CRYPTOPANIC_BASE}/posts/", params={"filter": "hot"}, timeout=5)
            print("API without key: HTTP", r.status_code, "(401=expected)")
        except Exception as e:
            print("API test error:", e)
        print("Add CRYPTOPANIC_API_KEY to .env (project root or backend/)")
    print("-" * 50)

    news = _get_crypto_news()
    if news:
        print(f"News via _get_crypto_news: {len(news)} items")
        for i, n in enumerate(news[:2], 1):
            print(f"  {i}. {(n.get('title') or '')[:60]}")
    else:
        print("News via _get_crypto_news: NONE")

    print("-" * 50)
    inst = get_btc_institutions()
    print("news_headlines count:", len(inst.get("news_headlines", [])))
    print("-" * 50)
    print("RESULT:", "OK" if news else "FAIL")

if __name__ == "__main__":
    main()
