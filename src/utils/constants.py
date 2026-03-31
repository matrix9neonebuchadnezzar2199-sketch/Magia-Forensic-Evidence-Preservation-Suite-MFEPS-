"""
MFEPS v2.1.0 — 定数定義
"""
import re

# アプリケーション情報
APP_NAME = "MFEPS"
APP_FULL_NAME = "Magia Forensic Evidence Preservation Suite"
APP_VERSION = "2.1.0"
APP_TITLE = f"{APP_NAME} — Forensic Evidence Preservation Suite v{APP_VERSION}"

# デフォルト設定値
DEFAULT_PORT = 8580
DEFAULT_BUFFER_SIZE = 1_048_576  # 1 MiB
DEFAULT_FONT_SIZE = 16
DEFAULT_THEME = "dark"
DEFAULT_OUTPUT_DIR = "./output"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_RETRY_COUNT = 3
DEFAULT_OPTICAL_RETRY_COUNT = 5

# バッファサイズ選択肢
BUFFER_SIZE_OPTIONS = {
    "256 KiB": 256 * 1024,
    "512 KiB": 512 * 1024,
    "1 MiB": 1_048_576,
    "2 MiB": 2 * 1_048_576,
    "4 MiB": 4 * 1_048_576,
}

# セクタサイズ
SECTOR_SIZE_BLOCK = 512       # USB/HDD/SSD
SECTOR_SIZE_DATA = 2048       # CD-ROM/DVD/BD (データ)
SECTOR_SIZE_AUDIO = 2352      # CD-DA (音楽)

# Windows API 定数
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_NO_BUFFERING = 0x20000000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
INVALID_HANDLE_VALUE = -1

# IOCTL 定数
IOCTL_DISK_GET_DRIVE_GEOMETRY = 0x00070000
IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
IOCTL_DISK_IS_WRITABLE = 0x00070024
IOCTL_CDROM_READ_TOC_EX = 0x00024054
IOCTL_CDROM_READ_TOC = 0x00024000

IOCTL_CDROM_RAW_READ = 0x0002403E
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x0004D014

# デフォルト RFC3161 TSA
DEFAULT_TSA_URL = "http://timestamp.digicert.com"

# 監査ログ ハッシュチェーン初期値
GENESIS_HASH_INPUT = "GENESIS"

# DVD 圧縮デフォルト目標サイズ
DVD5_TARGET_BYTES = 4_700_000_000  # DVD-5 (4.7 GB)
DVD9_TARGET_BYTES = 8_500_000_000  # DVD-9 (8.5 GB)

# UI カラー定数
COLOR_PRIMARY = "#6C63FF"
COLOR_SECONDARY = "#3D3D5C"
COLOR_BACKGROUND = "#0F0F1A"
COLOR_SURFACE = "#1A1A2E"
COLOR_HEADER = "#16213E"
COLOR_SIDEBAR = "#0F0F1A"
COLOR_SUCCESS = "#00E676"
COLOR_WARNING = "#FFD600"
COLOR_ERROR = "#FF5252"
COLOR_INFO = "#448AFF"
COLOR_TEXT_PRIMARY = "#E0E0E0"
COLOR_TEXT_SECONDARY = "#9E9E9E"

# =====================================================================
# E01 (ewfacquire) 定数
# =====================================================================

# セグメント分割サイズ (bytes)
# encase6 フォーマット: 最大 7.9 EiB, それ以外: 最大 1.9 GiB
E01_DEFAULT_SEGMENT_SIZE_BYTES = 1_500_000_000  # 1.4 GiB (ewfacquire デフォルト)
E01_SEGMENT_SIZE_OPTIONS = {
    "1.4 GiB (デフォルト)": 1_500_000_000,
    "1.9 GiB (旧形式上限)": 2_040_109_465,
    "2 GiB": 2_147_483_648,
    "4 GiB": 4_294_967_296,
}

# 圧縮: -c は "method:level" 形式
E01_DEFAULT_COMPRESSION_METHOD = "deflate"
E01_DEFAULT_COMPRESSION_LEVEL = "fast"
E01_SUPPORTED_COMPRESSION_METHODS = ["deflate"]
E01_SUPPORTED_COMPRESSION_LEVELS = ["none", "empty-block", "fast", "best"]

E01_DEFAULT_SECTORS_PER_CHUNK = 64
E01_DEFAULT_EWF_FORMAT = "encase6"
E01_DEFAULT_READ_ERROR_RETRIES = 2

# ewfacquire 進捗（Windows 20230405 等は 3 行ブロック: Status / acquired / completion）
E01_PROGRESS_PATTERN = re.compile(r"Status:\s+at\s+([\d.]+)%")
E01_ACQUIRED_PATTERN = re.compile(
    r"acquired\s+[\d.]+\s+\S+\s+\((\d+)\s+bytes\)\s+of\s+total\s+[\d.]+\s+\S+\s+\((\d+)\s+bytes\)"
)
E01_SPEED_PATTERN = re.compile(
    r"completion\s+in\s+(.+?)\s+with\s+([\d.]+)\s+\S+\s+\((\d+)\s+bytes/second\)"
)
# ハッシュ行: コロン後にタブのみのビルドあり。SHA-1 行は出ない場合あり（ewfverify で補完）
E01_HASH_PATTERN = re.compile(
    r"([A-Za-z0-9\-]+)\s+hash\s+calculated\s+over\s+data:\s*\t*([0-9a-fA-F]+)"
)
E01_WRITTEN_PATTERN = re.compile(
    r"Written:\s+[\d.]+\s+\S+\s+\((\d+)\s+bytes\)"
)
# 後方互換（統合テスト・旧コード向け）
E01_BYTES_PATTERN = E01_WRITTEN_PATTERN

EWFVERIFY_STORED_HASH_PATTERN = (
    r"([A-Za-z0-9\-]+)\s+hash\s+stored\s+in\s+file:\s*([0-9a-fA-F]+)"
)
EWFVERIFY_COMPUTED_HASH_PATTERN = (
    r"([A-Za-z0-9\-]+)\s+hash\s+calculated\s+over\s+data:\s*([0-9a-fA-F]+)"
)
EWFVERIFY_SUCCESS_PATTERN = r"ewfverify:\s+SUCCESS"

# E01 設定画面 UI 選択肢（値 → ラベル）
E01_COMPRESSION_OPTIONS = {
    "deflate:fast": "deflate / fast（推奨・高速）",
    "deflate:best": "deflate / best（最大圧縮）",
    "deflate:none": "deflate / none（無圧縮）",
    "deflate:empty-block": "deflate / empty-block（空ブロックのみ圧縮）",
}

E01_SEGMENT_SIZE_OPTIONS_UI = {
    "1500000000": "1.4 GiB（デフォルト）",
    "2040109465": "1.9 GiB（旧形式上限）",
    "2147483648": "2 GiB（encase6+）",
    "4294967296": "4 GiB（encase6+）",
}

E01_FORMAT_OPTIONS = {
    "encase5": "EnCase 5 (.E01)  — 最大互換",
    "encase6": "EnCase 6 (.E01)  — 2GiB超セグメント対応（推奨）",
    "encase7": "EnCase 7 (.E01)  — 最新",
    "ewfx": "EWFX (.Ex01)     — 拡張フォーマット",
}

# E01 残り時間パーサー（"completion in NN minute(s) and NN second(s) ..." から秒数を抽出）
E01_REMAINING_PATTERN = re.compile(
    r"completion\s+in\s+"
    r"(?:(\d+)\s+hour\(?s?\)?\s+and\s+)?"
    r"(\d+)\s+minute\(?s?\)?\s+and\s+"
    r"(\d+)\s+second"
)
