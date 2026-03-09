@echo off
REM Start Project SC frontend pointed at TEST backend (port 8000).
REM Run this in a separate terminal AFTER starting the backend with start_test.bat.
REM Ensures the app talks to TEST only (Crunchtime test + GYG-CT-Helper_TEST DB).
set VITE_API_BASE_URL=http://localhost:8000
cd /d "%~dp0frontend"
echo.
echo Frontend (TEST) - API target: http://localhost:8000
echo Backend must be running: start_test.bat
echo.
npm run dev
pause
