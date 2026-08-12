@echo off
title REL-UNITY - server
cd /d "%~dp0"

echo ============================================
echo   REL-UNITY  -  keep this window open
echo   http://localhost:8080/
echo ============================================
echo.

echo Checking GitHub for updates before starting...
git -C "%~dp0\.." pull
if errorlevel 1 (
  echo (Could not reach GitHub - starting with the code already on this PC.)
) else (
  echo Up to date.
)
echo.

REM ---- start the email->challan poller once, in its own window (keeps polling on its own) ----
if exist challan_watch.py (
  echo Starting the mill-challan email poller...
  start "REL-UNITY challan poller" cmd /k python challan_watch.py --loop
)
echo.

:loop
python server.py %*
echo.
echo Server stopped. Restarting in 3 seconds...
echo (Close this window, or press Ctrl+C twice, to quit for good.)
timeout /t 3 /nobreak >nul
goto loop
