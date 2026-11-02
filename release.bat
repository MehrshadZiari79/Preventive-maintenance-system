@echo off
rem ==========================================================================
rem  Gela PM System - ONE command release
rem
rem    release.bat                     build + publish (version +1)
rem    release.bat "release notes"     same, with a note shown in the manifest
rem
rem  Clients install the new version within ~15 minutes.
rem  Details of every run: release_logs\
rem ==========================================================================
setlocal
cd /d "%~dp0"
set "PY=C:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" release.py %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
