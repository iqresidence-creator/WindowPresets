@echo off
REM Launcher for WindowPresets
REM Uses the Python 3.14 install pinned via the py launcher.

setlocal
set "APP_DIR=%~dp0"
set "PYEXE=C:\Users\MY\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if not exist "%PYEXE%" (
    echo [run.bat] Python not found at: %PYEXE%
    echo [run.bat] Trying the "py" launcher instead...
    set "PYEXE=py -3.14"
)

cd /d "%APP_DIR%"
%PYEXE% main.py
if errorlevel 1 pause
endlocal
