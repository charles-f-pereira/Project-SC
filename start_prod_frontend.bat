@echo off
REM Start Project SC frontend pointed at PROD backend (port 8001).
REM Run this in a separate terminal AFTER starting the backend with start_prod.bat.
REM Ensures the app talks to PROD only (Crunchtime prod + GYG-CT-Helper_PROD DB).
set VITE_API_BASE_URL=http://localhost:8001
cd /d "%~dp0frontend"
echo.
echo Frontend (PROD) - API target: http://localhost:8001
echo Backend must be running: start_prod.bat
echo.
npm run dev
pause
