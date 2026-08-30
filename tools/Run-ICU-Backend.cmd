@echo off
set "DATABASE_URL=postgresql+psycopg2://pilot_app@127.0.0.1:55432/nurse_schedule_pilot_v2"
set "ENVIRONMENT=development"
if not defined FRONTEND_ORIGINS set "FRONTEND_ORIGINS=http://127.0.0.1:5174,http://localhost:5174"
cd /d "%~dp0..\backend"
"%~dp0..\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 >> "%~dp0..\.runtime\backend.log" 2>&1
