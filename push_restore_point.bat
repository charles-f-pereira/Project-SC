#@echo off
cd /d "%~dp0"

echo Running validation checks...
powershell -NoProfile -ExecutionPolicy Bypass -File ".\check.ps1"
if errorlevel 1 (
    echo.
    echo ❌ Checks failed. Commit aborted.
    pause
    exit /b 1
)

echo.
echo ✅ Checks passed. Committing...

git add .
git commit -m "restore point – %date% %time%"
git push

echo.
echo 🚀 Push complete.
pause