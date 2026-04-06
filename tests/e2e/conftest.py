"""
Playwright E2E テスト共通フィクスチャ。
NiceGUI を子プロセスで起動し、ブラウザインスタンスを提供する。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Browser, Page, sync_playwright


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    """NiceGUI アプリをバックグラウンドで起動し base_url を yield。"""
    tmp = tmp_path_factory.mktemp("e2e")
    port = _free_port()
    repo_root = Path(__file__).resolve().parents[2]
    env = {**os.environ}
    # 親 pytest の環境が子プロセスに伝播すると NiceGUI が「pytest モード」になり
    # NICEGUI_SCREEN_TEST_PORT を必須にするため除去する
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("NICEGUI_SCREEN_TEST_PORT", None)
    env.pop("NICEGUI_SCREEN_TEST_URL", None)
    env.update(
        {
            "MFEPS_OUTPUT_DIR": str(tmp / "output"),
            "MFEPS_DB_PATH": str(tmp / "mfeps_e2e.db"),
            "MFEPS_LOG_LEVEL": "WARNING",
            "MFEPS_PORT": str(port),
            "MFEPS_STORAGE_SECRET": "e2e-test-secret",
            "MFEPS_E2E_ADMIN_PASSWORD": "TestAdmin123!",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, str(repo_root / "src" / "main.py")],
        env=env,
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 45
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/login", timeout=2, follow_redirects=True)
            if r.status_code == 200:
                break
        except Exception as e:
            last_err = e
        if proc.poll() is not None:
            err = proc.stderr.read() if proc.stderr else b""
            raise RuntimeError(
                f"NiceGUI app exited early (code={proc.returncode}): {err[:4000]!r}"
            )
        time.sleep(0.5)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise RuntimeError(
            f"NiceGUI app failed to start within 45s (last_err={last_err!r})"
        )

    yield url

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser: Browser, app_url: str):
    ctx = browser.new_context()
    p = ctx.new_page()
    p.goto(app_url)
    yield p
    ctx.close()


@pytest.fixture
def authenticated_page(page: Page, app_url: str):
    """ログイン済みページを返す。"""
    page.goto(f"{app_url}/login")
    page.wait_for_selector("input", timeout=15000)
    page.locator("input").first.fill("admin")
    page.locator("input[type='password']").fill("TestAdmin123!")
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(f"{app_url}/", timeout=20000)
    return page
