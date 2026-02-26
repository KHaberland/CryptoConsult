@echo off
title CryptoConsult Backend
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.."
python -m venv venv 2>nul
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
python manage.py runserver
