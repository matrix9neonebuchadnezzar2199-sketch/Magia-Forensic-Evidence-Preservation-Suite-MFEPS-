"""
MFEPS v2.0 — エラーコード体系
E1xxx: システムエラー
E2xxx: デバイス検出エラー
E3xxx: イメージングエラー
E4xxx: 光学メディアエラー
E5xxx: ハッシュエラー
E6xxx: 報告書エラー
"""
from enum import Enum


class Severity(str, Enum):
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCode:
    """個別エラーコード定義"""

    def __init__(self, code: str, message_en: str, message_ja: str,
                 severity: Severity, recommendation: str = ""):
        self.code = code
        self.message_en = message_en
        self.message_ja = message_ja
        self.severity = severity
        self.recommendation = recommendation

    def __str__(self) -> str:
        return f"[{self.code}] {self.message_ja}"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message_en": self.message_en,
            "message_ja": self.message_ja,
            "severity": self.severity.value,
            "recommendation": self.recommendation,
        }


# ───── E1xxx: システムエラー ─────
E1001 = ErrorCode(
    "E1001", "Administrator privileges required",
    "管理者権限が必要です", Severity.CRITICAL,
    "start.bat を右クリック→「管理者として実行」してください")
E1002 = ErrorCode(
    "E1002", "Database connection failed",
    "データベース接続に失敗しました", Severity.CRITICAL,
    "data/ フォルダの書込権限を確認してください")
E1003 = ErrorCode(
    "E1003", "Output directory not writable",
    "出力先に書込みできません", Severity.ERROR,
    "出力先フォルダの存在と書込権限を確認してください")
E1004 = ErrorCode(
    "E1004", "Insufficient disk space",
    "ディスク容量が不足しています", Severity.ERROR,
    "出力先ドライブの空き容量を確認してください")

# ───── E2xxx: デバイス検出エラー ─────
E2001 = ErrorCode(
    "E2001", "WMI connection failed",
    "WMI 接続に失敗しました", Severity.ERROR,
    "WMI サービスが実行中か確認してください")
E2002 = ErrorCode(
    "E2002", "No devices detected",
    "デバイスが検出されませんでした", Severity.WARN,
    "USB デバイスが正しく接続されているか確認してください")
E2003 = ErrorCode(
    "E2003", "Device access denied",
    "デバイスへのアクセスが拒否されました", Severity.ERROR,
    "管理者権限で実行しているか確認してください")
E2004 = ErrorCode(
    "E2004", "Failed to get drive geometry",
    "ドライブジオメトリの取得に失敗しました", Severity.ERROR,
    "デバイスが正常に動作しているか確認してください")

# ───── E3xxx: イメージングエラー ─────
E3001 = ErrorCode(
    "E3001", "Failed to open source device",
    "ソースデバイスを開けません", Severity.CRITICAL,
    "デバイスが接続されているか、管理者権限があるか確認してください")
E3002 = ErrorCode(
    "E3002", "Failed to create output file",
    "出力ファイルの作成に失敗しました", Severity.ERROR,
    "出力先パスと権限を確認してください")
E3003 = ErrorCode(
    "E3003", "Sector read error (CRC)",
    "セクタ読取エラー（CRC）", Severity.WARN,
    "不良セクタはゼロ埋めされ、エラーマップに記録されます")
E3004 = ErrorCode(
    "E3004", "Write error",
    "書込みエラーが発生しました", Severity.ERROR,
    "出力先ディスクの状態を確認してください")
E3005 = ErrorCode(
    "E3005", "Buffer allocation failed",
    "バッファの確保に失敗しました", Severity.CRITICAL,
    "システムメモリが不足しています。バッファサイズを小さくしてください")
E3006 = ErrorCode(
    "E3006", "User cancelled",
    "ユーザーによりキャンセルされました", Severity.WARN,
    "")
E3007 = ErrorCode(
    "E3007", "Unexpected EOF",
    "予期せぬ EOF に到達しました", Severity.ERROR,
    "デバイスのサイズ情報が正しくない可能性があります")
E3010 = ErrorCode(
    "E3010", "Write block verification failed",
    "ライトブロック検証に失敗しました", Severity.CRITICAL,
    "ハードウェアライトブロッカーの使用を検討してください")

# ───── E4xxx: 光学メディアエラー ─────
E4001 = ErrorCode(
    "E4001", "No optical drive detected",
    "光学ドライブが検出されませんでした", Severity.ERROR,
    "光学ドライブが接続されているか確認してください")
E4002 = ErrorCode(
    "E4002", "No media inserted",
    "ドライブにメディアが挿入されていません", Severity.WARN,
    "ディスクを挿入してから再試行してください")
E4003 = ErrorCode(
    "E4003", "Failed to read TOC",
    "TOC の読取に失敗しました", Severity.ERROR,
    "ディスクが正しく挿入されているか確認してください")
E4004 = ErrorCode(
    "E4004", "Optical sector read error",
    "光学セクタ読取エラー（傷・劣化）", Severity.WARN,
    "ディスク表面の傷や汚れを確認してください")
E4005 = ErrorCode(
    "E4005", "pydvdcss initialization failed",
    "pydvdcss の初期化に失敗しました", Severity.ERROR,
    "libdvdcss-2.dll が libs/ に配置されているか確認してください")
E4006 = ErrorCode(
    "E4006", "AACS decryption failed",
    "AACS 復号に失敗しました", Severity.ERROR,
    "keydb.cfg が正しく配置されているか確認してください")

# ───── E5xxx: ハッシュエラー ─────
E5001 = ErrorCode(
    "E5001", "Hash calculation interrupted",
    "ハッシュ計算が中断されました", Severity.ERROR,
    "再度計算を実行してください")
E5002 = ErrorCode(
    "E5002", "Hash mismatch",
    "ハッシュ値が一致しません", Severity.CRITICAL,
    "ソースとイメージの完全性に問題があります。再イメージングを推奨します")
E5003 = ErrorCode(
    "E5003", "RFC3161 connection failed",
    "RFC3161 TSA サーバーへの接続に失敗しました", Severity.WARN,
    "ネットワーク接続とTSA URLを確認してください")

# ───── E6xxx: 報告書エラー ─────
E6001 = ErrorCode(
    "E6001", "Report template not found",
    "報告書テンプレートが見つかりません", Severity.ERROR,
    "templates/ フォルダにテンプレートファイルが存在するか確認してください")
E6002 = ErrorCode(
    "E6002", "PDF generation failed",
    "PDF 生成に失敗しました", Severity.ERROR,
    "ReportLab が正しくインストールされているか確認してください")

# 全エラーコードの辞書
ALL_ERROR_CODES: dict[str, ErrorCode] = {
    ec.code: ec for ec in [
        E1001, E1002, E1003, E1004,
        E2001, E2002, E2003, E2004,
        E3001, E3002, E3003, E3004, E3005, E3006, E3007, E3010,
        E4001, E4002, E4003, E4004, E4005, E4006,
        E5001, E5002, E5003,
        E6001, E6002,
    ]
}


def get_error(code: str) -> ErrorCode | None:
    """エラーコード文字列から ErrorCode オブジェクトを取得"""
    return ALL_ERROR_CODES.get(code)
