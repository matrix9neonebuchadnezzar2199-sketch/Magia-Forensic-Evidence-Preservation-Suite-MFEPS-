# MFEPS v2.0 — ポータブル環境構築スクリプト
# Python Embedded + 依存パッケージ + DLL の自動セットアップ

param(
    [string]$PythonVersion = "3.11.9"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  MFEPS ポータブル環境構築" -ForegroundColor Cyan
Write-Host "  Python Embedded $PythonVersion" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. runtime/ ディレクトリ作成 ---
$RuntimeDir = Join-Path $ScriptDir "runtime"
if (-Not (Test-Path $RuntimeDir)) {
    New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
    Write-Host "[1/6] runtime/ ディレクトリ作成" -ForegroundColor Green
} else {
    Write-Host "[1/6] runtime/ ディレクトリ既存" -ForegroundColor Yellow
}

# --- 2. Python Embedded ダウンロード ---
$PythonZip = "python-$PythonVersion-embed-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZip"
$ZipPath = Join-Path $ScriptDir $PythonZip

if (-Not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    Write-Host "[2/6] Python Embedded ダウンロード中..." -ForegroundColor Green
    Invoke-WebRequest -Uri $PythonUrl -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $RuntimeDir -Force
    Remove-Item $ZipPath
    Write-Host "      -> 展開完了" -ForegroundColor Green
} else {
    Write-Host "[2/6] Python Embedded 既存" -ForegroundColor Yellow
}

# --- 3. python311._pth 編集 (import site 有効化) ---
$PthFile = Get-ChildItem -Path $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    $PthContent = Get-Content $PthFile.FullName
    $PthContent = $PthContent -replace "^#import site", "import site"
    Set-Content -Path $PthFile.FullName -Value $PthContent
    Write-Host "[3/6] import site 有効化完了" -ForegroundColor Green
} else {
    Write-Host "[3/6] _pth ファイルが見つかりません" -ForegroundColor Red
}

# --- 4. pip インストール ---
$PipExe = Join-Path $RuntimeDir "Scripts\pip.exe"
if (-Not (Test-Path $PipExe)) {
    Write-Host "[4/6] pip インストール中..." -ForegroundColor Green
    $GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
    $GetPipPath = Join-Path $ScriptDir "get-pip.py"
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath
    & (Join-Path $RuntimeDir "python.exe") $GetPipPath
    Remove-Item $GetPipPath
    Write-Host "      -> pip インストール完了" -ForegroundColor Green
} else {
    Write-Host "[4/6] pip 既存" -ForegroundColor Yellow
}

# --- 5. 依存パッケージインストール ---
Write-Host "[5/6] 依存パッケージインストール中..." -ForegroundColor Green
$RequirementsPath = Join-Path $ScriptDir "requirements.txt"
& (Join-Path $RuntimeDir "python.exe") -m pip install -r $RequirementsPath --quiet
Write-Host "      -> 依存パッケージインストール完了" -ForegroundColor Green

# --- 6. libs/ ディレクトリ確認 ---
$LibsDir = Join-Path $ScriptDir "libs"
if (-Not (Test-Path $LibsDir)) {
    New-Item -ItemType Directory -Path $LibsDir | Out-Null
}
Write-Host "[6/6] libs/ ディレクトリ確認完了" -ForegroundColor Green

# --- 検証 ---
Write-Host ""
Write-Host "======= セットアップ検証 =======" -ForegroundColor Cyan
& (Join-Path $RuntimeDir "python.exe") -c "import nicegui; print('  nicegui:', nicegui.__version__)"
& (Join-Path $RuntimeDir "python.exe") -c "import sqlalchemy; print('  sqlalchemy:', sqlalchemy.__version__)"
& (Join-Path $RuntimeDir "python.exe") -c "import ctypes; print('  ctypes: OK (kernel32 =', ctypes.windll.kernel32, ')')"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  セットアップ完了！" -ForegroundColor Green
Write-Host "  start.bat をダブルクリックで起動できます" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

Write-Host "[NOTE] 以下のDLLは別途配置が必要です:" -ForegroundColor Yellow
Write-Host "  libs/libdvdcss-2.dll  — DVD CSS解除用 (VideoLAN公式サイトから)" -ForegroundColor Yellow
Write-Host "  libs/libaacs.dll      — BD AACS解除用 (オプション)" -ForegroundColor Yellow
Write-Host "  libs/ffmpeg.exe       — 映像圧縮用 (gyan.dev から)" -ForegroundColor Yellow
