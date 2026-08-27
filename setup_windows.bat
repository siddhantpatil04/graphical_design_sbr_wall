@echo off
setlocal
cd /d "%~dp0"
echo Creating virtual environment...
py -m venv .venv
if errorlevel 1 goto :error

echo Installing dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Setup complete.
echo Run run_app.bat to start the application.
pause
exit /b 0
:error
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
