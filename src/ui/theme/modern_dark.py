"""
MFEPS — モダンダークテーマ（Cursor 系パレット）
参照: https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/cursor/DESIGN.md
"""
from src.utils.constants import (
    COLOR_PRIMARY,
    COLOR_SECONDARY,
    COLOR_BACKGROUND,
    COLOR_SURFACE,
    COLOR_HEADER,
    COLOR_SIDEBAR,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_PRIMARY_RGB,
)

# Quasar 用テーマカラー設定
QUASAR_BRAND_COLORS = {
    "primary": COLOR_PRIMARY,
    "secondary": COLOR_SECONDARY,
    "accent": COLOR_PRIMARY,
    "dark": COLOR_BACKGROUND,
    "dark-page": COLOR_BACKGROUND,
    "positive": COLOR_SUCCESS,
    "negative": COLOR_ERROR,
    "info": COLOR_INFO,
    "warning": COLOR_WARNING,
}

# カスタムCSS
CUSTOM_CSS = f"""
/* ===== MFEPS Dark — Cursor-inspired ===== */
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap');

:root {{
    --mfeps-primary: {COLOR_PRIMARY};
    --mfeps-secondary: {COLOR_SECONDARY};
    --mfeps-bg: {COLOR_BACKGROUND};
    --mfeps-surface: {COLOR_SURFACE};
    --mfeps-surface-400: #35332e;
    --mfeps-surface-500: #403e39;
    --mfeps-header: {COLOR_HEADER};
    --mfeps-sidebar: {COLOR_SIDEBAR};
    --mfeps-success: {COLOR_SUCCESS};
    --mfeps-warning: {COLOR_WARNING};
    --mfeps-error: {COLOR_ERROR};
    --mfeps-info: {COLOR_INFO};
    --mfeps-text: {COLOR_TEXT_PRIMARY};
    --mfeps-text-secondary: {COLOR_TEXT_SECONDARY};
    --mfeps-border: rgba(230, 229, 224, 0.1);
    --mfeps-accent-soft: rgba({COLOR_PRIMARY_RGB}, 0.12);
    --mfeps-accent-mid: rgba({COLOR_PRIMARY_RGB}, 0.2);
    --mfeps-accent-table: rgba({COLOR_PRIMARY_RGB}, 0.1);
    --mfeps-accent-row: rgba({COLOR_PRIMARY_RGB}, 0.06);
}}

body {{
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--mfeps-bg) !important;
    color: var(--mfeps-text) !important;
}}

body .q-page, .nicegui-content {{
    font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
}}

.q-header, .q-drawer, .q-btn, .q-field, .q-table, .q-dialog {{
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}}

/* ヘッダー */
.q-header {{
    background: var(--mfeps-header) !important;
    border-bottom: 1px solid var(--mfeps-border) !important;
}}

/* サイドバー */
.q-drawer {{
    background: var(--mfeps-sidebar) !important;
    border-right: 1px solid var(--mfeps-border) !important;
}}

.q-drawer .q-item {{
    border-radius: 8px;
    margin: 2px 8px;
    transition: background 0.2s ease, color 0.2s ease;
}}

.q-drawer .q-item:hover {{
    background: var(--mfeps-accent-soft) !important;
}}

.q-drawer .q-item--active {{
    background: var(--mfeps-accent-mid) !important;
    color: var(--mfeps-primary) !important;
}}

/* カード */
.q-card {{
    background: var(--mfeps-surface) !important;
    border: 1px solid var(--mfeps-border) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.q-card:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45) !important;
}}

/* ボタン */
.q-btn {{
    border-radius: 8px !important;
    text-transform: none !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em;
}}

/* テーブル */
.q-table {{
    background: var(--mfeps-surface) !important;
    border-radius: 8px !important;
}}

.q-table thead th {{
    background: var(--mfeps-accent-table) !important;
    color: var(--mfeps-text) !important;
    font-weight: 600 !important;
}}

.q-table tbody tr:hover {{
    background: var(--mfeps-accent-row) !important;
}}

/* プログレスバー */
.q-linear-progress {{
    border-radius: 4px !important;
    height: 8px !important;
}}

/* ダイアログ */
.q-dialog__inner > .q-card {{
    background: var(--mfeps-surface) !important;
    border-radius: 8px !important;
    border: 1px solid var(--mfeps-border) !important;
}}

/* ステッパー */
.q-stepper {{
    background: transparent !important;
    box-shadow: none !important;
}}

.q-stepper__step-inner {{
    background: var(--mfeps-surface);
    border-radius: 8px;
    padding: 20px;
    border: 1px solid var(--mfeps-border);
}}

/* ステータスバッジ */
.badge-success {{
    background: {COLOR_SUCCESS} !important;
    color: #0c0c0c !important;
    font-weight: 600;
}}

.badge-warning {{
    background: {COLOR_WARNING} !important;
    color: #0c0c0c !important;
    font-weight: 600;
}}

.badge-error {{
    background: {COLOR_ERROR} !important;
    color: #fff !important;
    font-weight: 600;
}}

.badge-info {{
    background: {COLOR_INFO} !important;
    color: #fff !important;
    font-weight: 600;
}}

/* モノスペース（ハッシュ値表示） */
.hash-mono {{
    font-family: ui-monospace, 'Cascadia Code', 'Consolas', monospace;
    font-size: 0.85em;
    letter-spacing: 0.04em;
    word-break: break-all;
}}

/* スクロールバー */
::-webkit-scrollbar {{
    width: 8px;
    height: 8px;
}}

::-webkit-scrollbar-track {{
    background: rgba(0, 0, 0, 0.2);
}}

::-webkit-scrollbar-thumb {{
    background: rgba({COLOR_PRIMARY_RGB}, 0.35);
    border-radius: 4px;
}}

::-webkit-scrollbar-thumb:hover {{
    background: rgba({COLOR_PRIMARY_RGB}, 0.55);
}}

/* セクションヘッダー */
.section-header {{
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--mfeps-text-secondary);
    padding: 16px 16px 4px 16px;
}}

/* アニメーション */
@keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

.fade-in {{
    animation: fadeIn 0.3s ease-out;
}}

@keyframes pulse-glow {{
    0%, 100% {{ box-shadow: 0 0 5px rgba({COLOR_PRIMARY_RGB}, 0.25); }}
    50% {{ box-shadow: 0 0 16px rgba({COLOR_PRIMARY_RGB}, 0.45); }}
}}

.pulse-glow {{
    animation: pulse-glow 2s ease-in-out infinite;
}}

"""


def get_font_size_css(size: int) -> str:
    """フォントサイズを動的に変更するCSS"""
    return f"body {{ font-size: {size}px !important; }}"
