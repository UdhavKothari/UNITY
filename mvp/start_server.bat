@echo off
title REL Dyeing ERP - server
cd /d "%~dp0"

echo ============================================
echo   REL Dyeing ERP  -  keep this window open
echo   http://localhost:8080/
echo ============================================
echo.

:loop
python server.py %*
echo.
echo Server stopped. Restarting in 3 seconds...
echo (Close this window, or press Ctrl+C twice, to quit for good.)
timeout /t 3 /nobreak >nul
goto loop
