@echo off
REM One-command bootstrap for Windows.
REM Creates the venv, installs dependencies, and seeds .env from the template.

setlocal enabledelayedexpansion

echo.
echo === folder_access_agent setup ===
echo.

REM ---- Step 1: confirm Python is available ----
py --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python launcher 'py' was not found on your PATH.
    echo.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo During install, tick "Add Python to PATH".
    echo.
    exit /b 1
)

REM ---- Step 2: create the virtual environment ----
if exist .venv\Scripts\python.exe (
    echo [1/3] Virtual environment already exists, skipping creation.
) else (
    echo [1/3] Creating virtual environment in .venv ...
    py -m venv .venv
    if errorlevel 1 (
        echo ERROR: failed to create virtual environment.
        exit /b 1
    )
)

REM ---- Step 3: install dependencies ----
echo [2/3] Installing dependencies (this takes a couple of minutes the first time) ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. See the output above.
    exit /b 1
)

REM ---- Step 4: seed .env if missing ----
if exist .env (
    echo [3/3] .env already exists, leaving it alone.
) else (
    echo [3/3] Creating .env from .env.example ...
    copy .env.example .env >nul
)

echo.
echo ============================================================
echo  Setup complete.
echo.
echo  Next steps:
echo.
echo    1. Open .env and set your OpenAI API key:
echo         notepad .env
echo.
echo    2. Build the policy index (one-time, needs your API key):
echo         python -m rag.ingest
echo.
echo    3. Start the app:
echo         streamlit run app.py
echo.
echo  Whenever you open a new Command Prompt to work on this project,
echo  re-activate the venv first:
echo         .venv\Scripts\activate.bat
echo ============================================================
echo.
endlocal
