@echo off
chcp 65001 >nul
title Day ma nguon len GitHub
cd /d "%~dp0"

echo ========================================================
echo   Dang day ma nguon len GitHub:
echo   https://github.com/ngo-trieu/msstore-package-downloader
echo ========================================================
echo.

git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo [OK] Da day thanh cong toan bo ma nguon len GitHub!
) else (
    echo.
    echo [LOI] Khong the push. Hay kiem tra lai quyen truy cap hoac mang.
)

echo.
pause
