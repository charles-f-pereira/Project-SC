@echo off
REM ============================================================================
REM Project SC – TEST environment (backend only)
REM ============================================================================
REM Uses backend\.env with CT_ENV=test. Do NOT set APP_ENV (production uses that).
REM PostgreSQL: backend\.env must define pgName, pgPassword, pgDatabase=GYG-CT-Helper_TEST
REM   so orders persist and the Review page shows transactions.
REM ============================================================================
echo.
echo Backend (TEST) starting on http://localhost:8000
echo   Crunchtime: TEST  ^|  DB: from .env (pgDatabase=GYG-CT-Helper_TEST)
echo.
echo In a SECOND terminal run:  start_test_frontend.bat
echo   (so the frontend uses this TEST backend only)
echo Then open the URL shown (e.g. http://localhost:5175) in your browser.
echo.
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
