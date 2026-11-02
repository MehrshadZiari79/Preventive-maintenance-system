@echo off
rem Gela PM System - add the machine-hours tables to PM_Database (run once)
setlocal
cd /d "%~dp0"
set "PY=C:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" db_setup.py
echo.
pause
