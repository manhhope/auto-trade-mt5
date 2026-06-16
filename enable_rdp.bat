@echo off
echo ===================================================
echo   KICH HOAT REMOTE DESKTOP (RDP) - PORT 3389
echo ===================================================
echo.

:: Check for administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [Loi] Vui long nhap chuot phai vao file nay va chon "Run as administrator"!
    echo.
    pause
    exit /b 1
)

:: Enable RDP in registry
echo Dang cap nhat Registry...
reg add "HKLM\System\CurrentControlSet\Control\Terminal Server" /v fDenyTSConnections /t REG_DWORD /d 0 /f

if %errorLevel% equ 0 (
    echo [+] Registry fDenyTSConnections da duoc dat ve 0 (Cho phep ket noi).
) else (
    echo [Loi] Khong the cap nhat Registry.
    pause
    exit /b 1
)

:: Set TermService to Automatic and Restart
echo.
echo Dang khoi dong lai dich vu Remote Desktop...
sc config TermService start= auto
net stop TermService /y
net start TermService

echo.
echo ===================================================
echo [+] Cấu hình hoàn tất!
echo   Vui lòng kiểm tra xem cổng 3389 đã mở chưa.
echo ===================================================
pause
