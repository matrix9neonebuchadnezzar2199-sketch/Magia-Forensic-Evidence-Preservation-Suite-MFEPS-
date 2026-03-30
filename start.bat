@echo off
setlocal EnableExtensions EnableDelayedExpansion
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

echo [WARN] 管理者権限が必要です。UAC 昇格を実行します...
echo.
echo 続行すると「ユーザーアカウント制御」が表示されます。
pause
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
exit /b 0

:run
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
set "DVDCSS_LIBRARY=%~dp0libs\libdvdcss-2.dll"
set "PATH=%~dp0libs;%PATH%"

set "MFEPS_LOG=%TEMP%\mfeps_start.log"
echo [%date% %time%] MFEPS start.bat :run> "%MFEPS_LOG%"
echo CD=%CD%>> "%MFEPS_LOG%"

if exist "runtime\python.exe" (
    echo [INFO] ポータブル Python を使用します
    echo runtime\python.exe>> "%MFEPS_LOG%"
    "runtime\python.exe" --version >> "%MFEPS_LOG%" 2>&1
    "runtime\python.exe" -u src\main.py
    set "EXITCODE=!ERRORLEVEL!"
    echo exit=!EXITCODE!>> "%MFEPS_LOG%"
    if not "!EXITCODE!"=="0" goto :pyerr
    goto :done_ok
)

where py >nul 2>&1
if %errorLevel%==0 (
    echo [INFO] Python Launcher を使用します (py -3)
    echo py -3>> "%MFEPS_LOG%"
    py -3 --version >> "%MFEPS_LOG%" 2>&1
    py -3 -u src\main.py
    set "EXITCODE=!ERRORLEVEL!"
    echo exit=!EXITCODE!>> "%MFEPS_LOG%"
    if not "!EXITCODE!"=="0" goto :pyerr
    goto :done_ok
)

where python >nul 2>&1
if not %errorLevel%==0 (
    echo [ERROR] python / py が PATH に見つかりません。
    echo Python 3 をインストールするか、runtime\python.exe を配置してください。
    goto :pyerr
)

echo [INFO] システムの python を使用します
echo python>> "%MFEPS_LOG%"
python --version >> "%MFEPS_LOG%" 2>&1
python -u src\main.py
set "EXITCODE=!ERRORLEVEL!"
echo exit=!EXITCODE!>> "%MFEPS_LOG%"
if not "!EXITCODE!"=="0" goto :pyerr

:done_ok
echo.
echo [INFO] MFEPS を終了しました。
echo ログ: %MFEPS_LOG%
pause
exit /b 0

:pyerr
echo.
echo [ERROR] 起動に失敗しました。
echo ログ: %MFEPS_LOG%
if exist "%MFEPS_LOG%" type "%MFEPS_LOG%"
pause
exit /b 1
