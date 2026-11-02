@echo off
rem ==========================================================================
rem  Gela PM System - test the automatic updates on this PC
rem  (Start menu: PM System > Test automatic updates)
rem  Asks for administrator rights, runs test_autoupdate.ps1, keeps the window
rem  open so the result can be read. The report is also saved to
rem  %ProgramData%\GelaDairy\PMSystem\updater\last_test_report.txt
rem ==========================================================================
setlocal
net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)
title PM System - automatic update test
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0test_autoupdate.ps1"
echo.
pause
endlocal
