@echo off
REM ---- Mill-challan email poller (standalone) ----
REM Keeps checking osbyrel@gmail.com every couple of minutes and imports challan PDFs.
REM start_server.bat already launches this for you; run this only if you want it on its own.
REM One-time on this PC:  pip install pdfplumber   and put the Gmail app password in secrets.local.json
title REL-UNITY - challan poller
cd /d "%~dp0"
:loop
python challan_watch.py --loop
echo.
echo Poller stopped. Restarting in 5 seconds...  (close this window to quit)
timeout /t 5 /nobreak >nul
goto loop
