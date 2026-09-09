@echo off
setlocal
cd /d "%~dp0"

echo ZeeNoodle starter
echo You can run this file again anytime.
echo.
set "UPDATED=0"

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
    echo Warning: git is not installed. Updates and local GitHub backup need git.
)

echo.
echo ========================================
echo Your .env settings
echo ========================================
%PY% envutil.py
echo.
set /p DOSETUP=Open the setup form to fill in or change these? [y/N]: 
if /i "%DOSETUP%"=="y" goto RUNSETUP
if /i "%DOSETUP%"=="yes" goto RUNSETUP
goto AFTERSETUP

:RUNSETUP
%PY% setup.py
if errorlevel 1 (
    echo Setup failed.
    pause
    exit /b 1
)
echo.
echo Settings after the form:
%PY% envutil.py

:AFTERSETUP
echo.
set /p DOUPD=Update ZeeNoodle from GitHub first? [y/N]: 
if /i "%DOUPD%"=="y" goto DOUPDATE
if /i "%DOUPD%"=="yes" goto DOUPDATE
goto AFTERUPDATE

:DOUPDATE
if not exist ".git" (
    echo This folder is not a git repo, so there is nothing to pull.
    echo Clone your own repo, or skip update.
    goto AFTERUPDATE
)
where git >nul 2>&1
if errorlevel 1 (
    echo git is required to update. Install git, then run start.bat again.
    pause
    exit /b 1
)
echo Pulling latest code...
git pull --ff-only
if errorlevel 1 (
    echo git pull failed. Fix the repo, then run start.bat again.
    pause
    exit /b 1
)
echo Reinstalling Python packages...
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed after update.
    pause
    exit /b 1
)
set "UPDATED=1"
echo Local files updated. Next we can refresh the copy you already host.

:AFTERUPDATE
echo.
echo Where do you want to host ZeeNoodle?
echo   1. Quaxly  (quaxly.com)
echo   2. Waifly  (waifly.com) -- recommended if Quaxly is full
echo   3. Self-host on this PC or your own server
echo.
set /p HOSTCHOICE=Choose 1, 2, or 3: 
if "%HOSTCHOICE%"=="1" goto QUAXLY
if "%HOSTCHOICE%"=="2" goto WAIFLY
if "%HOSTCHOICE%"=="3" goto SELFHOST
echo Unknown choice.
pause
exit /b 1

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
if "%UPDATED%"=="1" (
    echo Refreshing the ZeeNoodle bot already on Quaxly.
    %PY% deploy.py --update
) else (
    echo Starting the Quaxly helper. Log in at quaxly.com in your browser.
    %PY% deploy.py
)
pause
exit /b 0

:WAIFLY
echo.
echo Waifly path: Discord app first (if needed), then the upload walkthrough.
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
if "%UPDATED%"=="1" (
    echo Refreshing the ZeeNoodle bot already on Waifly.
    %PY% deploy.py --waifly --update
) else (
    echo Starting the Waifly helper. Log in at waifly.com in your browser.
    %PY% deploy.py --waifly
)
pause
exit /b 0

:SELFHOST
echo.
echo Self-host: you keep the bot running on your own PC or server.
echo.
echo 1. First-time Discord setup (creates .env)
echo 2. Run ZeeNoodle on this Windows PC now
echo 3. Show how to run it on your own server
echo 4. Update from GitHub, then return to this menu
echo.
set /p CHOICE=Choose 1, 2, 3, or 4: 

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
    echo 7. To update later, run start.bat again and choose Update from GitHub.
    echo.
    pause
    exit /b 0
)
if "%CHOICE%"=="4" goto DOUPDATE_SELF

echo Unknown choice.
pause
exit /b 1

:DOUPDATE_SELF
if not exist ".git" (
    echo This folder is not a git repo, so there is nothing to pull.
    goto SELFHOST
)
where git >nul 2>&1
if errorlevel 1 (
    echo git is required to update.
    goto SELFHOST
)
echo Pulling latest code...
git pull --ff-only
if errorlevel 1 (
    echo git pull failed.
    pause
    goto SELFHOST
)
echo Reinstalling Python packages...
%PY% -m pip install -r requirements.txt
echo Local files updated.
set /p RUNNOW=Restart ZeeNoodle on this PC now? [y/N]: 
if /i "%RUNNOW%"=="y" goto RUNLOCAL
if /i "%RUNNOW%"=="yes" goto RUNLOCAL
echo Stop the old process, then choose 2 when you are ready.
goto SELFHOST

:RUNLOCAL
if not exist ".env" (
    echo No .env yet. Starting Discord setup first...
    %PY% setup.py
)
echo Starting the updated bot. Close any old ZeeNoodle window first.
%PY% bot.py
pause
exit /b 0

echo Unknown choice.
pause
exit /b 1
