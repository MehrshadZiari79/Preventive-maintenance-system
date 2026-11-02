@echo off
rem ==========================================================================
rem  Gela PM System - re-opens the application after a silent update.
rem
rem  Started (hidden, as the logged-in user) by PM_System.exe just before it
rem  closes itself for an update. Waits until the SYSTEM updater reports the
rem  update as finished (status "done"/"failed"/"idle"), then starts the app
rem  again. Gives up waiting after about 15 minutes and starts the app anyway.
rem
rem  usage: relaunch.cmd "<path to PM_System.exe>"
rem ==========================================================================
setlocal
set "APP=%~1"
set "STATUS=%ProgramData%\GelaDairy\PMSystem\updater\status\status.json"
set /a WAITED=0

rem give the updater a moment to switch from "pending" to "installing"
ping -n 6 127.0.0.1 >nul

:wait
if %WAITED% GEQ 900 goto start
findstr /c:"\"pending\"" /c:"\"installing\"" "%STATUS%" >nul 2>&1
if errorlevel 1 goto settle
ping -n 4 127.0.0.1 >nul
set /a WAITED+=3
goto wait

:settle
rem let Setup finish writing files and exit
ping -n 4 127.0.0.1 >nul

:start
if exist "%APP%" start "" "%APP%"
endlocal
exit /b 0
