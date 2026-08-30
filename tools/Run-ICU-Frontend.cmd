@echo off
cd /d "%~dp0..\frontend"
"C:\Program Files\nodejs\node.exe" "%~dp0..\frontend\node_modules\vite\bin\vite.js" --host 0.0.0.0 --port 5174 >> "%~dp0..\.runtime\frontend.log" 2>&1
