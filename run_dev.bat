@echo off
echo Starting Cafe des Artistes Bot in development mode...

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed! Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Check if virtual environment exists, if not create it
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install/upgrade dependencies
echo Installing/upgrading dependencies...
python -m pip install --upgrade pip
pip install -r src/requirements.txt

:: Run the bot
echo Starting the bot...
python src/main.py

:: Keep the window open if there's an error
pause 