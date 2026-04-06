"""agent_main エントリのスモーク（WebSocket は Phase 11）"""
from __future__ import annotations

import sys
from unittest.mock import patch


def test_agent_main_invokes_argparse():
    from src.agent import agent_main

    with patch.object(
        sys,
        "argv",
        ["agent_main", "--server", "ws://127.0.0.1:9/ws", "--id", "A1", "--secret", "sec"],
    ):
        agent_main.main()
