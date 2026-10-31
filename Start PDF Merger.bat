@echo off
cd /d "%~dp0"
python -I scripts\bootstrap.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -I -S scripts\run_app.py
if errorlevel 1 goto failed
exit /b
:failed
echo Could not start PDF Merger. See the error above.
echo Requires 64-bit Python 3.11 and verified wheels. See README.md for setup.
pause
