@echo off
REM Start Project SC backend (PROD): Crunchtime prod + GYG-CT-Helper_PROD DB
REM Run from project root. Sets APP_ENV=production to load backend\.env.production (CT_ENV=prod).
echo.
echo Backend (PROD) starting on http://localhost:8001
echo APP_ENV=production is set so backend loads .env.production (Crunchtime prod + GYG-CT-Helper_PROD).
echo.
echo To use the app, open a SECOND terminal and run:
echo   PowerShell:  $env:VITE_API_BASE_URL="http://localhost:8001"; cd frontend; npm run dev
echo   Cmd:        set VITE_API_BASE_URL=http://localhost:8001 ^&^& cd frontend ^&^& npm run dev
echo Or run:  start_prod_frontend.bat
echo Then open the URL shown (e.g. http://localhost:5175) in your browser.
echo.
cd /d "%~dp0backend"
set APP_ENV=production
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
pause
