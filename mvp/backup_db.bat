@echo off
REM Daily ERP database backup — point Windows Task Scheduler at this file.
cd /d "%~dp0"
python backup_db.py >> backups\backup.log 2>&1
