@echo off
REM ---- Mill-challan email poller (ONE run) ----
REM Checks osbyrel@gmail.com once and imports any new challan PDFs, then exits.
REM Point Windows Task Scheduler at this file to run it on a schedule (e.g. every 30 min).
REM One-time on this PC:  pip install pdfplumber   and put the Gmail app password in secrets.local.json
cd /d "%~dp0"
python challan_watch.py
