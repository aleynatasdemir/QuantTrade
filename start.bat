@echo off
echo ========================================
echo QuantTrade - Quick Start Script
echo ========================================
echo.

REM Check if .env exists in backend
if not exist "backend\.env" (
    echo [!] Creating backend/.env from .env.example...
    copy "backend\.env.example" "backend\.env"
    echo.
    echo [!] IMPORTANT: Edit backend/.env and add your Telegram bot token!
    echo     1. Open backend/.env
    echo     2. Set TELEGRAM_BOT_TOKEN=your_actual_token
    echo.
    pause
)

REM Check if backend dependencies are installed
echo [1/4] Checking backend dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing backend dependencies...
    cd backend
    pip install -r requirements.txt
    cd ..
) else (
    echo Backend dependencies OK
)
echo.

REM Check if frontend dependencies are installed
echo [2/4] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
) else (
    echo Frontend dependencies OK
)
echo.

REM Start backend in new window
echo [3/4] Starting backend server...
start "QuantTrade Backend" cmd /k "cd backend && python main.py"
timeout /t 3 >nul
echo.

REM Start frontend in new window
echo [4/4] Starting frontend dev server...
start "QuantTrade Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 3 >nul
echo.

echo ========================================
echo QuantTrade is starting!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo To start Telegram bot, run:
echo   python telegram_bot_standalone.py
echo.
echo Press any key to exit this window...
pause >nul
