@echo off
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    mshta "javascript:var sh=new ActiveXObject('WScript.Shell');sh.Popup('Python не найден. Установите Python 3.10+ с https://python.org',0,'CryptoConsult',0x10);close()"
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    mshta "javascript:var sh=new ActiveXObject('WScript.Shell');sh.Popup('Node.js не найден. Установите Node.js 18+ с https://nodejs.org',0,'CryptoConsult',0x10);close()"
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0backend\start-backend.bat' -WindowStyle Hidden"
timeout /t 3 /nobreak >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0frontend\start-frontend.bat' -WindowStyle Hidden"
timeout /t 45 /nobreak >nul

start http://localhost:3000
