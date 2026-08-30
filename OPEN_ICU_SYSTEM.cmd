@echo off
setlocal
rem The browser launcher uses port 5174. Pass the matching origins to FastAPI
rem before any child process starts so login preflight requests are accepted.
set "FRONTEND_ORIGINS=http://127.0.0.1:5174,http://localhost:5174"
call "%~dp0tools\Start-ICU-System.cmd"
set "OPEN_ICU_EXIT=%ERRORLEVEL%"
endlocal & exit /b %OPEN_ICU_EXIT%
