@echo off
REM Start frontend pointed at PROD backend (port 8001). Run this in a separate terminal after start_prod.bat.
set VITE_API_BASE_URL=http://localhost:8001
cd /d "%~dp0frontend"
npm run dev
pause
