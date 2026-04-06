"""
MFEPS Agent エントリーポイント
Usage: python -m src.agent.agent_main --server ws://host:port/ws/agent --id AGENT01 --secret mysecret
"""
from __future__ import annotations

import argparse
import logging


def main() -> None:
    parser = argparse.ArgumentParser(description="MFEPS Remote Agent")
    parser.add_argument("--server", required=True, help="WebSocket URL")
    parser.add_argument("--id", required=True, help="Agent ID")
    parser.add_argument("--secret", required=True, help="Shared secret")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    from src.agent.agent_service import AgentService

    AgentService(server_url=args.server, agent_id=args.id, secret=args.secret)
    print(
        f"Agent {args.id} initialized. WebSocket connection will be available in Phase 11."
    )


if __name__ == "__main__":
    main()
