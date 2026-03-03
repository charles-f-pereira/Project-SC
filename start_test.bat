@echo off
REM Start Project SC backend (TEST): Crunchtime test + GYG-CT-Helper_TEST DB
REM Run from project root. Uses backend\.env (CT_ENV=test). Do not set APP_ENV.
echo.
echo Backend (TEST) starting on http://localhost:8000
echo To use the app, open a SECOND terminal and run:
echo   cd frontend
echo   npm run dev
echo Then open the URL shown (e.g. http://localhost:5175) in your browser.
echo.
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
