@echo off
REM ---- Pull the latest code from GitHub and restart the ERP ----
REM Run this on the factory PC whenever there's an update on GitHub.
cd /d "%~dp0\.."
echo Pulling latest code from GitHub...
git pull
if errorlevel 1 (
  echo.
  echo Git pull failed. Check the internet/VPN connection and try again.
  pause
  exit /b 1
)
echo.
echo Restarting the server so backend changes take effect...
REM The start_server.bat loop relaunches python automatically after it is stopped.
taskkill /f /im python.exe >nul 2>&1
echo Done. If the server window did not reappear, double-click start_server.bat.
timeout /t 3 /nobreak >nul
