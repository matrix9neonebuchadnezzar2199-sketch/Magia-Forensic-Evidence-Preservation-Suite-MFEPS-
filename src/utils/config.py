"""
MFEPS v2.0 — 設定管理
.env ファイルからの読込 + Pydantic バリデーション
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


def _get_base_dir() -> Path:
    """mfeps/ ディレクトリのルートパスを取得"""
    return Path(__file__).resolve().parent.parent.parent


class MFEPSConfig(BaseSettings):
    """アプリケーション全体の設定"""

    # サーバー
    mfeps_port: int = Field(default=8580, description="WebUI ポート番号")
    bind_address: str = Field(
        default="127.0.0.1",
        description="バインドアドレス（127.0.0.1 でローカルのみ）",
    )
    session_timeout_hours: int = Field(
        default=8, ge=1, le=168, description="セッション有効期限（時間）"
    )

    # 出力
    mfeps_output_dir: str = Field(default="./output", description="出力先ディレクトリ")

    # イメージング
    mfeps_buffer_size: int = Field(default=1_048_576, description="バッファサイズ (bytes)")

    # テーマ
    mfeps_theme: str = Field(default="dark", description="テーマ (dark/light)")
    mfeps_font_size: int = Field(default=16, ge=12, le=24, description="フォントサイズ (px)")

    # RFC3161
    mfeps_rfc3161_enabled: bool = Field(default=False, description="RFC3161 タイムスタンプ有効化")
    mfeps_rfc3161_tsa_url: str = Field(
        default="http://timestamp.digicert.com", description="TSA サーバー URL")

    # 光学メディア
    mfeps_double_read_optical: bool = Field(
        default=False, description="光学メディア二回読取検証")

    # ログ
    mfeps_log_level: str = Field(default="INFO", description="ログレベル")

    # DLL
    dvdcss_library: str = Field(
        default="./libs/libdvdcss-2.dll", description="libdvdcss DLL パス")

    # AACS (Blu-ray)
    aacs_library: str = Field(
        default="./libs/libaacs.dll", description="libaacs DLL パス")
    aacs_keydb_path: str = Field(
        default="", description="AACS keydb.cfg パス（空の場合は復号スキップ）")

    # MakeMKV（将来のバックエンドB用）
    makemkvcon_path: str = Field(
        default="", description="makemkvcon パス（空の場合は未使用）")

    # E01 (ewfacquire / ewfverify)
    ewfacquire_path: str = Field(
        default="",
        description=(
            "ewfacquire.exe のパス（空なら base_dir/libs/ewfacquire.exe 等を自動検索）"
        ),
    )
    ewfverify_path: str = Field(
        default="",
        description=(
            "ewfverify.exe のパス（空なら base_dir/libs/ewfverify.exe 等を自動検索）"
        ),
    )
    e01_segment_size_bytes: int = Field(
        default=1_500_000_000,
        ge=1_048_576,
        description="E01 セグメントファイルサイズ (bytes)",
    )
    e01_compression_method: str = Field(
        default="deflate",
        description="E01 圧縮方式 (deflate)",
    )
    e01_compression_level: str = Field(
        default="fast",
        description="E01 圧縮レベル (none / empty-block / fast / best)",
    )
    e01_ewf_format: str = Field(
        default="encase6",
        description="EWF 出力フォーマット (encase5 / encase6 / encase7)",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def base_dir(self) -> Path:
        return _get_base_dir()

    @property
    def output_dir(self) -> Path:
        p = Path(self.mfeps_output_dir)
        if not p.is_absolute():
            p = self.base_dir / p
        return p

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "mfeps.db"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.base_dir / "reports"

    @property
    def templates_dir(self) -> Path:
        return self.base_dir / "templates"

    @property
    def backup_dir(self) -> Path:
        return self.base_dir / "backup"

    @property
    def libs_dir(self) -> Path:
        return self.base_dir / "libs"

    def _candidate_paths_for_tool(
        self, configured: str, exe_name: str
    ) -> list[Path]:
        """設定値（相対は base_dir 基準）のあと、libs/ と libs/ewftools-x64/ を試す。"""
        seen: set[str] = set()
        out: list[Path] = []

        def add(p: Path) -> None:
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                out.append(p.resolve())

        if (configured or "").strip():
            p = Path(configured.strip())
            if not p.is_absolute():
                p = (self.base_dir / p).resolve()
            else:
                p = p.resolve()
            add(p)

        libs = self.base_dir / "libs"
        add(libs / exe_name)
        add(libs / "ewftools-x64" / exe_name)
        return out

    def resolve_ewfacquire_path(self) -> str:
        """利用する ewfacquire.exe の絶対パス（見つからなければ空文字）。"""
        for p in self._candidate_paths_for_tool(self.ewfacquire_path, "ewfacquire.exe"):
            if p.is_file():
                return str(p)
        return ""

    def resolve_ewfverify_path(self) -> str:
        """利用する ewfverify.exe の絶対パス（見つからなければ空文字）。"""
        for p in self._candidate_paths_for_tool(self.ewfverify_path, "ewfverify.exe"):
            if p.is_file():
                return str(p)
        return ""

    @property
    def ewfacquire_available(self) -> bool:
        return bool(self.resolve_ewfacquire_path())

    @property
    def ewfverify_available(self) -> bool:
        return bool(self.resolve_ewfverify_path())


# シングルトン設定インスタンス
_config: MFEPSConfig | None = None


def get_config() -> MFEPSConfig:
    """設定シングルトンを取得"""
    global _config
    if _config is None:
        env_path = _get_base_dir() / ".env"
        if env_path.exists():
            os.environ.setdefault("ENV_FILE", str(env_path))
        _config = MFEPSConfig(_env_file=str(env_path) if env_path.exists() else None)
    return _config


def reload_config() -> MFEPSConfig:
    """設定を再読込"""
    global _config
    _config = None
    return get_config()
