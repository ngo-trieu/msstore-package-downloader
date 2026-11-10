@echo off
title Build MS Store Downloader EXE (Nuitka)
echo ========================================================
echo   Bien dich MS Store Downloader sang EXE bang Nuitka
echo   Giao dien Native Tkinter sieu nhe (~10MB)
echo ========================================================
echo.

set "PY_CMD="

REM 1. Thu bang py launcher
py -3 --version >nul 2>nul
if %errorlevel% equ 0 set "PY_CMD=py -3"

REM 2. Thu bang python tren PATH
if not defined PY_CMD (
    where python >nul 2>nul
    if %errorlevel% equ 0 set "PY_CMD=python"
)

REM 3. Thu duong dan mac dinh Python 3.12
if not defined PY_CMD (
    if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
    )
)

if not defined PY_CMD (
    echo [ERROR] Khong tim thay Python!
    pause
    exit /b 1
)

echo [*] Python duoc su dung: %PY_CMD%

REM Kiem tra hoac cai dat Nuitka va zstandard
echo [*] Kiem tra thu vien Nuitka...
%PY_CMD% -m pip install -q nuitka zstandard

echo.
echo [*] Dang tien hanh bien dich sang C++ va ma may...
echo [*] Luu y: Lan dau bien dich Nuitka co the mat tu 2 - 5 phut
echo     (Nuitka se tu dong tai bo trinh bien dich MinGW64 neu chua co).
echo.

%PY_CMD% -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico="%~dp0assets\app.ico" ^
    --include-data-dir="%~dp0assets=assets" ^
    --enable-plugin=tk-inter ^
    --assume-yes-for-downloads ^
    --output-dir=dist ^
    --output-filename=MSStoreDownloader.exe ^
    app.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo [OK] Bien dich thanh cong!
    echo File EXE nam tai: %~dp0dist\MSStoreDownloader.exe
    echo ========================================================
    explorer "%~dp0dist"
) else (
    echo.
    echo [!] Co loi trong qua trinh bien dich.
)

pause
