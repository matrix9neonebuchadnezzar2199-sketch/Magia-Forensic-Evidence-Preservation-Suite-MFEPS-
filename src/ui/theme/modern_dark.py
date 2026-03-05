"""
MFEPS v2.0 — モダンダークテーマ
NiceGUI のカスタムCSS + Quasar 設定
"""
from src.utils.constants import (
    COLOR_PRIMARY, COLOR_SECONDARY, COLOR_BACKGROUND, COLOR_SURFACE,
    COLOR_HEADER, COLOR_SIDEBAR, COLOR_SUCCESS, COLOR_WARNING,
    COLOR_ERROR, COLOR_INFO, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
)

# Quasar 用テーマカラー設定
QUASAR_BRAND_COLORS = {
    "primary": COLOR_PRIMARY,
    "secondary": COLOR_SECONDARY,
    "accent": "#9C27B0",
    "dark": COLOR_BACKGROUND,
    "dark-page": COLOR_BACKGROUND,
    "positive": COLOR_SUCCESS,
    "negative": COLOR_ERROR,
    "info": COLOR_INFO,
    "warning": COLOR_WARNING,
}

# カスタムCSS
CUSTOM_CSS = f"""
/* ===== MFEPS Modern Dark Theme ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
    --mfeps-primary: {COLOR_PRIMARY};
    --mfeps-secondary: {COLOR_SECONDARY};
    --mfeps-bg: {COLOR_BACKGROUND};
    --mfeps-surface: {COLOR_SURFACE};
    --mfeps-header: {COLOR_HEADER};
    --mfeps-sidebar: {COLOR_SIDEBAR};
    --mfeps-success: {COLOR_SUCCESS};
    --mfeps-warning: {COLOR_WARNING};
    --mfeps-error: {COLOR_ERROR};
    --mfeps-info: {COLOR_INFO};
    --mfeps-text: {COLOR_TEXT_PRIMARY};
    --mfeps-text-secondary: {COLOR_TEXT_SECONDARY};
}}

body {{
    font-family: 'Inter', 'Segoe UI', sans-serif;
    background-color: var(--mfeps-bg) !important;
    color: var(--mfeps-text) !important;
}}

/* ヘッダー */
.q-header {{
    background: linear-gradient(135deg, {COLOR_HEADER}, {COLOR_SURFACE}) !important;
    border-bottom: 1px solid rgba(108, 99, 255, 0.2) !important;
    backdrop-filter: blur(10px);
}}

/* サイドバー */
.q-drawer {{
    background: {COLOR_SIDEBAR} !important;
    border-right: 1px solid rgba(108, 99, 255, 0.15) !important;
}}

.q-drawer .q-item {{
    border-radius: 8px;
    margin: 2px 8px;
    transition: all 0.2s ease;
}}

.q-drawer .q-item:hover {{
    background: rgba(108, 99, 255, 0.12) !important;
}}

.q-drawer .q-item--active {{
    background: rgba(108, 99, 255, 0.2) !important;
    color: {COLOR_PRIMARY} !important;
}}

/* カード */
.q-card {{
    background: {COLOR_SURFACE} !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.q-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4) !important;
}}

/* ボタン */
.q-btn {{
    border-radius: 8px !important;
    text-transform: none !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em;
}}

/* テーブル */
.q-table {{
    background: {COLOR_SURFACE} !important;
    border-radius: 12px !important;
}}

.q-table thead th {{
    background: rgba(108, 99, 255, 0.1) !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}

.q-table tbody tr:hover {{
    background: rgba(108, 99, 255, 0.06) !important;
}}

/* プログレスバー */
.q-linear-progress {{
    border-radius: 4px !important;
    height: 8px !important;
}}

/* ダイアログ */
.q-dialog__inner > .q-card {{
    background: {COLOR_SURFACE} !important;
    border-radius: 16px !important;
}}

/* ステッパー */
.q-stepper {{
    background: transparent !important;
    box-shadow: none !important;
}}

.q-stepper__step-inner {{
    background: {COLOR_SURFACE};
    border-radius: 12px;
    padding: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
}}

/* ステータスバッジ */
.badge-success {{
    background: {COLOR_SUCCESS} !important;
    color: #000 !important;
    font-weight: 600;
}}

.badge-warning {{
    background: {COLOR_WARNING} !important;
    color: #000 !important;
    font-weight: 600;
}}

.badge-error {{
    background: {COLOR_ERROR} !important;
    color: #FFF !important;
    font-weight: 600;
}}

.badge-info {{
    background: {COLOR_INFO} !important;
    color: #FFF !important;
    font-weight: 600;
}}

/* モノスペース（ハッシュ値表示） */
.hash-mono {{
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 0.85em;
    letter-spacing: 0.05em;
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
    background: rgba(108, 99, 255, 0.3);
    border-radius: 4px;
}}

::-webkit-scrollbar-thumb:hover {{
    background: rgba(108, 99, 255, 0.5);
}}

/* セクションヘッダー */
.section-header {{
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {COLOR_TEXT_SECONDARY};
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
    0%, 100% {{ box-shadow: 0 0 5px rgba(108, 99, 255, 0.3); }}
    50% {{ box-shadow: 0 0 20px rgba(108, 99, 255, 0.6); }}
}}

.pulse-glow {{
    animation: pulse-glow 2s ease-in-out infinite;
}}
"""


def get_font_size_css(size: int) -> str:
    """フォントサイズを動的に変更するCSS"""
    return f"body {{ font-size: {size}px !important; }}"
