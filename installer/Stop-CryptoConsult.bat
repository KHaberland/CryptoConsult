@echo off
echo Stopping CryptoConsult...
taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq CryptoConsult Backend" 2>nul
taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq CryptoConsult Frontend" 2>nul
echo Done.
timeout /t 2 /nobreak >nul
