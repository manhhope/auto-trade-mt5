@echo off
title Setup Telegram Account
echo ===================================================
echo [!] BAT DAU DANG NHAP TAI KHOAN TELEGRAM CA NHAN
echo ===================================================
echo.
echo Hay dam bao ban da dien dung TELEGRAM_API_ID va TELEGRAM_API_HASH vao file .env
echo.
.\venv\Scripts\python login_telethon.py
echo.
echo ===================================================
echo [+] Thiet lap hoan tat!
echo ===================================================
pause
