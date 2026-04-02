"""
MFEPS v2.3.0 — ライトモード CSS
"""

LIGHT_CSS = """
/* ---- MFEPS Light Theme ---- */
body.mfeps-light {
    --mfeps-bg: #F5F5F5;
    --mfeps-surface: #FFFFFF;
    --mfeps-header: #3D3D5C;
    --mfeps-sidebar: #FAFAFA;
    --mfeps-text-primary: #212121;
    --mfeps-text-secondary: #616161;
    --mfeps-border: #E0E0E0;
}

body.mfeps-light .q-header {
    background: var(--mfeps-header) !important;
}

body.mfeps-light .q-drawer {
    background: var(--mfeps-sidebar) !important;
    border-right: 1px solid var(--mfeps-border) !important;
}

body.mfeps-light .q-drawer .q-btn {
    color: var(--mfeps-text-primary) !important;
}

body.mfeps-light .q-page, body.mfeps-light .nicegui-content {
    background: var(--mfeps-bg) !important;
    color: var(--mfeps-text-primary) !important;
}

body.mfeps-light .q-card {
    background: var(--mfeps-surface) !important;
    color: var(--mfeps-text-primary) !important;
    border: 1px solid var(--mfeps-border);
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
    background: #F0F0F0 !important;
    color: #333 !important;
}

body.mfeps-light .q-table th {
    background: #EEEEEE !important;
}
"""
