@echo off
setlocal enabledelayedexpansion

set "REPO_URL=https://github.com/raviphdm23-a11y/banking-credit-risk.git"
set "REPO_DIR=banking-credit-risk"
set "BASE_DIR=%~dp0"

echo ============================================================
echo   Banking Credit Risk Calculator - Setup and Run
echo ============================================================
echo.

REM ---- Check Git is available ----
where git >nul 2>nul
if errorlevel 1 (
    echo ERROR: Git is not installed or not on PATH.
    echo Install it from https://git-scm.com/downloads and re-run this file.
    pause
    exit /b 1
)

REM ---- Check Python is available, prefer 3.10 via the py launcher ----
set "PYCMD="
py -3.10 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    set "PYCMD=py -3.10"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python is not installed or not on PATH.
        echo Install Python 3.10 from https://www.python.org/downloads/ and re-run this file.
        pause
        exit /b 1
    )
    set "PYCMD=python"
    echo WARNING: Python 3.10 not found via the "py" launcher - falling back to "python".
    echo          This project is built and tested against Python 3.10; other versions may not work.
)

REM ---- Clone (or update) the repository ----
cd /d "%BASE_DIR%"
if exist "%REPO_DIR%\.git" (
    echo Repository already present in "%REPO_DIR%" - pulling latest changes...
    pushd "%REPO_DIR%"
    git pull
    if errorlevel 1 (
        echo ERROR: git pull failed. Resolve any local changes/conflicts in "%REPO_DIR%" and re-run.
        popd
        pause
        exit /b 1
    )
    popd
) else (
    echo Cloning repository into "%REPO_DIR%"...
    git clone "%REPO_URL%" "%REPO_DIR%"
    if errorlevel 1 (
        echo ERROR: git clone failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

cd /d "%BASE_DIR%%REPO_DIR%"

REM ---- Create the virtual environment if it doesn't exist yet ----
if exist "venv310\Scripts\python.exe" (
    echo Virtual environment already exists - skipping creation.
) else (
    echo Creating virtual environment "venv310"...
    %PYCMD% -m venv venv310
    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM ---- Install dependencies ----
echo Installing dependencies from requirements.txt (this can take a few minutes on first run)...
"venv310\Scripts\python.exe" -m pip install --upgrade pip >nul
"venv310\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed - see the messages above for details.
    pause
    exit /b 1
)

REM ---- Start the Flask app in its own window ----
echo Starting the Flask app...
start "Banking Credit Risk Calculator" "venv310\Scripts\python.exe" app.py

REM ---- Wait for the server to come up, then open the browser ----
echo Waiting for the server to become ready...
set /a WAITED=0

:WAITLOOP
curl -s -o nul -w "%%{http_code}" http://localhost:5000/api/health > "%TEMP%\_bcr_health.txt" 2>nul
set /p HTTP_CODE=<"%TEMP%\_bcr_health.txt"
if "%HTTP_CODE%"=="200" goto SERVER_UP
set /a WAITED+=1
if %WAITED% GEQ 30 goto SERVER_TIMEOUT
timeout /t 1 /nobreak >nul
goto WAITLOOP

:SERVER_UP
echo Server is up.
goto OPEN_BROWSER

:SERVER_TIMEOUT
echo WARNING: The server did not respond within 30 seconds - opening the browser anyway.
echo          Check the "Banking Credit Risk Calculator" console window for errors.

:OPEN_BROWSER
start "" "http://localhost:5000"
del "%TEMP%\_bcr_health.txt" >nul 2>nul

echo.
echo ============================================================
echo   Done. The app is running in a separate console window.
echo   Close that window (or press Ctrl+C in it) to stop the server.
echo ============================================================
pause
