@echo off
REM ============================================================
REM   AI Trading Guardian - double-click launcher (Windows)
REM   Just double-click this file. It does everything for you.
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo    AI TRADING GUARDIAN - starting up...
echo ============================================================
echo.

REM 1) Find Python.
where python >nul 2>&1
if %errorlevel%==0 (
    set PY=python
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set PY=py
    ) else (
        echo [X] Python is not installed.
        echo     Please install it from https://www.python.org/downloads/
        echo     IMPORTANT: tick "Add Python to PATH" during install, then try again.
        echo.
        pause
        exit /b 1
    )
)
echo [OK] Found Python.

REM 2) Install required packages (quietly; only if missing).
echo Checking/installing required packages (first run may take a minute)...
%PY% -m pip install --user --quiet -r requirements.txt

REM 3) Open the browser automatically after a short delay.
start "" cmd /c "timeout /t 4 >nul & start http://localhost:8000"

REM 4) Start the app.
echo.
echo Starting the dashboard...
echo Your browser will open automatically at:  http://localhost:8000
echo.
echo  ^>^>^>  To STOP the system completely: close this window, or press Ctrl+C  ^<^<^<
echo ============================================================
echo.
set PYTHONPATH=.
%PY% trading_bot\main.py

echo.
echo AI Trading Guardian has stopped.
pause
