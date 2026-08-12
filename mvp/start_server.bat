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

REM ---- check email for challans ONCE, in this same window (recurring polls: use Task Scheduler) ----
if exist challan_watch.py (
  echo Checking email for new mill challans...
  python challan_watch.py
)
echo.

:loop
python server.py %*
echo.
echo Server stopped. Restarting in 3 seconds...
echo (Close this window, or press Ctrl+C twice, to quit for good.)
timeout /t 3 /nobreak >nul
goto loop
