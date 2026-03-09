@echo off
REM ============================================================================
REM Project SC – PRODUCTION environment (backend only)
REM ============================================================================
REM Sets APP_ENV=production so backend loads backend\.env.production (CT_ENV=prod).
REM PostgreSQL: .env.production must define pgName, pgPassword, pgDatabase=GYG-CT-Helper_PROD.
REM ============================================================================
echo.
echo Backend (PROD) starting on http://localhost:8001
echo   APP_ENV=production - loads .env.production (Crunchtime prod + GYG-CT-Helper_PROD)
echo.
echo In a SECOND terminal run:  start_prod_frontend.bat
echo   (so the frontend uses this PROD backend only)
echo Then open the URL shown (e.g. http://localhost:5175) in your browser.
echo.
cd /d "%~dp0backend"
set APP_ENV=production
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
pause
