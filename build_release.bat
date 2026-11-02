@echo off
rem ==========================================================================
rem  Gela PM System - build + package one release (run on the build PC)
rem
rem    1. edit version.txt  (e.g. 2.4.1)
rem    2. build_release.bat
rem    3. test the installer on ONE client
rem    4. publish:
rem       python publish_update.py installer_output\PM_System_Setup_v<ver>.exe <ver> \\192.168.0.1\PM_System_Updates
rem ==========================================================================
setlocal
cd /d "%~dp0"

set /p VER=<version.txt
for /f "tokens=* delims= " %%a in ("%VER%") do set VER=%%a
if "%VER%"=="" (echo version.txt is empty & exit /b 1)

set "PY=C:\ProgramData\anaconda3\python.exe"
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not exist "database\db_secrets.py" (
  echo database\db_secrets.py is missing - copy database\db_secrets.example.py and fill it in.
  exit /b 1
)

echo === Building PM System %VER% ===
"%PY%" -m PyInstaller --noconfirm --clean PM_System.spec || goto fail

echo === Packaging installer ===
"%ISCC%" /DAppVersion=%VER% Setup.iss || goto fail

echo.
echo Done: installer_output\PM_System_Setup_v%VER%.exe
echo Test it on one PC, then publish with:
echo   "%PY%" publish_update.py installer_output\PM_System_Setup_v%VER%.exe %VER% \\192.168.0.1\PM_System_Updates
exit /b 0

:fail
echo BUILD FAILED
exit /b 1
