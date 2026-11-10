@echo off
chcp 65001 >nul
title Microsoft Store Package Downloader
echo ==================================================
echo   Microsoft Store Package Downloader
echo   Direct FE3 API - No 3rd party needed
echo ==================================================
echo.

set "PY_CMD="

REM 1. Python launcher
py -3 --version >nul 2>nul
if %errorlevel% equ 0 set "PY_CMD=py -3"

REM 2. python tren PATH
if not defined PY_CMD (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PY_CMD=python"
)

REM 3. Duong dan mac dinh Python 3.12
if not defined PY_CMD (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
    )
)

if not defined PY_CMD (
    echo [ERROR] Khong tim thay Python. Hay cai dat Python 3.10+ va tick "Add to PATH".
    pause
    exit /b 1
)

echo [*] Python: %PY_CMD%
%PY_CMD% --version

echo.
echo [*] Dang kiem tra thu vien...
%PY_CMD% -m pip install -q -r "%~dp0requirements.txt"

REM Tao icon neu chua co
if not exist "%~dp0assets\app.ico" (
    %PY_CMD% "%~dp0make_icon.py"
)

echo.
echo [*] Dang khoi dong ung dung...
%PY_CMD% "%~dp0app.py"

if %errorlevel% neq 0 (
    echo.
    echo [!] Ung dung da dong hoac co loi.
    pause
)
