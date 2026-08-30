@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-ICU-System.ps1" -StartMobile
if errorlevel 1 timeout /t 10 /nobreak >nul
