@echo off
chcp 65001 > nul
echo ============================================
echo   MFEPS - Forensic Evidence Preservation
echo   Suite v2.0 (Portable)
echo ============================================
echo.

REM --- 管理者権限チェック ---
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] 管理者権限で実行中です
    goto :run
)

echo [WARN] 管理者権限が必要です。UAC昇格を実行します...
powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
exit /b

:run
cd /d "%~dp0"

REM --- 環境変数設定 ---
if exist "runtime\python.exe" (
    echo [INFO] ポータブル Python を使用します
    set PYTHON_HOME=%~dp0runtime
    set PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%PATH%
    set PYTHONPATH=%~dp0
    set DVDCSS_LIBRARY=%~dp0libs\libdvdcss-2.dll
    set PATH=%~dp0libs;%PATH%
    "%PYTHON_HOME%\python.exe" src\main.py
) else (
    echo [INFO] システム Python を使用します
    set PYTHONPATH=%~dp0
    set DVDCSS_LIBRARY=%~dp0libs\libdvdcss-2.dll
    set PATH=%~dp0libs;%PATH%
    python src\main.py
)

pause
