@echo off
echo Setting up Python virtual environment...

REM Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not found in PATH
    pause
    exit /b 1
)

REM Set the name of the virtual environment
set VENV_NAME=venv

REM Create virtual environment if it doesn't exist
if not exist %VENV_NAME% (
    echo Creating virtual environment...
    python -m venv %VENV_NAME%
)

REM Check if virtual environment was created successfully
if not exist %VENV_NAME%\Scripts\activate.bat (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate the virtual environment
echo Activating virtual environment...
call %VENV_NAME%\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

REM Check if installation was successful
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to install some dependencies
    call deactivate
    pause
    exit /b 1
)

echo Setup completed successfully!
echo Run run_scraper.bat to start the monitoring script
call deactivate
pause