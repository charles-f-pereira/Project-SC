@echo off
cd /d "%~dp0"
git add .
git commit -m "restore point – %date% %time%"
git push
