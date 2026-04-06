"""
MFEPS — ライトモード CSS（Cursor 系 warm light）
参照: https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/cursor/DESIGN.md
"""

LIGHT_CSS = """
/* ---- MFEPS Light — Cursor-inspired ---- */
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap');

body.mfeps-light {
    --mfeps-bg: #f2f1ed;
    --mfeps-surface: #faf9f5;
    --mfeps-surface-raised: #ffffff;
    --mfeps-header: #26251e;
    --mfeps-sidebar: #faf9f5;
    --mfeps-text-primary: #26251e;
    --mfeps-text-secondary: #6e6d66;
    --mfeps-border: rgba(38, 37, 30, 0.12);
    --mfeps-accent: #f54e00;
    --mfeps-accent-soft: rgba(245, 78, 0, 0.08);
    --mfeps-accent-mid: rgba(245, 78, 0, 0.14);
}

body.mfeps-light {
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    color: var(--mfeps-text-primary) !important;
}

body.mfeps-light .q-page,
body.mfeps-light .nicegui-content {
    font-family: 'Source Serif 4', Georgia, 'Times New Roman', serif;
}

body.mfeps-light .q-header {
    background: var(--mfeps-header) !important;
    color: #f2f1ed !important;
    border-bottom: 1px solid var(--mfeps-border) !important;
}

body.mfeps-light .q-drawer {
    background: var(--mfeps-sidebar) !important;
    border-right: 1px solid var(--mfeps-border) !important;
}

body.mfeps-light .q-drawer .q-btn {
    color: var(--mfeps-text-primary) !important;
}

body.mfeps-light .q-drawer .q-item:hover {
    background: var(--mfeps-accent-soft) !important;
}

body.mfeps-light .q-drawer .q-item--active {
    background: var(--mfeps-accent-mid) !important;
    color: var(--mfeps-accent) !important;
}

body.mfeps-light .q-page, body.mfeps-light .nicegui-content {
    background: var(--mfeps-bg) !important;
    color: var(--mfeps-text-primary) !important;
}

body.mfeps-light .q-card {
    background: var(--mfeps-surface-raised) !important;
    color: var(--mfeps-text-primary) !important;
    border: 1px solid var(--mfeps-border) !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 2px rgba(38, 37, 30, 0.06) !important;
}

body.mfeps-light .q-footer {
    background: var(--mfeps-surface) !important;
    color: var(--mfeps-text-secondary) !important;
    border-top: 1px solid var(--mfeps-border) !important;
}

body.mfeps-light .section-header {
    color: var(--mfeps-text-secondary) !important;
}

body.mfeps-light .hash-mono {
    background: rgba(38, 37, 30, 0.06) !important;
    color: #26251e !important;
    font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
}

body.mfeps-light .q-table th {
    background: rgba(245, 78, 0, 0.06) !important;
}

body.mfeps-light .q-table tbody tr:hover {
    background: rgba(245, 78, 0, 0.04) !important;
}
"""
