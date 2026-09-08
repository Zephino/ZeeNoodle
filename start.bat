@echo off
setlocal
cd /d "%~dp0"

echo ZeeNoodle starter
echo Default: install the bot on Quaxly (https://quaxly.com/).
echo.

set "PY="
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3"
) else (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo Python was not found.
    where winget >nul 2>&1
    if errorlevel 1 (
        echo Opening https://www.python.org/downloads/
        echo Enable "Add python.exe to PATH", then run start.bat again.
        start "" "https://www.python.org/downloads/"
        pause
        exit /b 1
    )
    echo Installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo Close this window and run start.bat again so PATH updates.
    pause
    exit /b 1
)

echo Installing Python packages...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed.
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo Warning: git is not installed. Local GitHub backup needs git. Quaxly can still use the GitHub API.
)

echo.
echo Host on Quaxly by default.
set /p HOSTQ=Use Quaxly? [Y/n]: 
if /i "%HOSTQ%"=="n" goto SELFHOST
if /i "%HOSTQ%"=="no" goto SELFHOST

:QUAXLY
echo.
echo Quaxly path: Discord app first (if needed), then the upload walkthrough.
if not exist ".env" (
    echo No .env yet. Starting Discord setup...
    %PY% setup.py
    if errorlevel 1 (
        echo Setup failed.
        pause
        exit /b 1
    )
)
echo.
echo Starting the Quaxly helper. Log in at quaxly.com in your browser.
%PY% deploy.py
pause
exit /b 0

:SELFHOST
echo.
echo Self-host: you keep the bot running on your own PC or server.
echo.
echo 1. First-time Discord setup (creates .env)
echo 2. Run ZeeNoodle on this Windows PC now
echo 3. Show how to run it on your own server
echo.
set /p CHOICE=Choose 1, 2, or 3: 

if "%CHOICE%"=="1" (
    %PY% setup.py
    pause
    exit /b 0
)
if "%CHOICE%"=="2" (
    if not exist ".env" (
        echo No .env yet. Starting Discord setup first...
        %PY% setup.py
        if errorlevel 1 (
            echo Setup failed.
            pause
            exit /b 1
        )
    )
    echo Starting ZeeNoodle. Leave this window open.
    %PY% bot.py
    pause
    exit /b 0
)
if "%CHOICE%"=="3" (
    echo.
    echo How to host ZeeNoodle on your own server
    echo.
    echo 1. Copy this whole project folder to the server.
    echo 2. Install Python 3.12+ and git if you want local GitHub backup.
    echo 3. In the project folder run: python -m pip install -r requirements.txt
    echo 4. Create .env from .env.example. Set DISCORD_TOKEN and INCIDENT_CHANNEL_ID.
    echo    Leave GITHUB_REMOTE and GITHUB_TOKEN blank unless they are YOURS.
    echo 5. Start and keep it running: python bot.py
    echo 6. On Windows you can use Task Scheduler to run start.bat after login.
    echo    On Linux use systemd or screen/tmux so it restarts after reboot.
    echo.
    pause
    exit /b 0
)

echo Unknown choice.
pause
exit /b 1
