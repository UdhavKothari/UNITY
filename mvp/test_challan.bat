@echo off
REM ---- Test the challan email poller and KEEP THE WINDOW OPEN so you can read the result ----
REM Use this to check your Gmail setup. For the scheduled/automatic run, use start_challan.bat.
title REL-UNITY - challan poller (test)
cd /d "%~dp0"
echo Running the challan email poller once...
echo.
python challan_watch.py
echo.
echo ------------------------------------------------------------
echo Done. (A full log is also saved to inbox_challan\challan.log)
echo ------------------------------------------------------------
pause
