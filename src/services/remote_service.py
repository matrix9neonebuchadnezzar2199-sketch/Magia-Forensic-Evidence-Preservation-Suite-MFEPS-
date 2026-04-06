"""
MFEPS — リモートイメージング管理サービス（サーバー側）
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("mfeps.remote_service")


@dataclass
class AgentInfo:
    agent_id: str
    hostname: str
    ip: str
    capabilities: dict = field(default_factory=dict)
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_heartbeat: str = ""
    status: str = "online"


@dataclass
class RemoteJobState:
    job_id: str
    agent_id: str
    status: str = "pending"
    progress: dict = field(default_factory=dict)
    result: Optional[dict] = None


class RemoteService:
    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._jobs: dict[str, RemoteJobState] = {}

    def register_agent(
        self,
        agent_id: str,
        hostname: str,
        ip: str,
        capabilities: dict | None = None,
    ) -> bool:
        if agent_id in self._agents:
            logger.warning("Agent already registered: %s", agent_id)
            return False
        self._agents[agent_id] = AgentInfo(
            agent_id=agent_id,
            hostname=hostname,
            ip=ip,
            capabilities=capabilities or {},
        )
        logger.info("Agent registered: %s (%s)", agent_id, hostname)
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        logger.info("Agent unregistered: %s", agent_id)
        return True

    def heartbeat(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.last_heartbeat = datetime.now(timezone.utc).isoformat()
        agent.status = "online"
        return True

    def get_agents(self) -> list[dict]:
        return [
            {
                "agent_id": a.agent_id,
                "hostname": a.hostname,
                "ip": a.ip,
                "status": a.status,
                "last_heartbeat": a.last_heartbeat,
            }
            for a in self._agents.values()
        ]

    def get_agent(self, agent_id: str) -> Optional[dict]:
        a = self._agents.get(agent_id)
        if not a:
            return None
        return {
            "agent_id": a.agent_id,
            "hostname": a.hostname,
            "ip": a.ip,
            "status": a.status,
            "capabilities": a.capabilities,
        }

    def start_remote_imaging(
        self,
        agent_id: str,
        device_path: str,
        case_id: str,
        evidence_id: str,
        options: dict | None = None,
    ) -> str:
        del device_path, case_id, evidence_id, options  # Phase 11 で使用
        if agent_id not in self._agents:
            raise ValueError(f"Agent not found: {agent_id}")
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = RemoteJobState(job_id=job_id, agent_id=agent_id, status="pending")
        logger.info("Remote imaging job created: %s on agent %s", job_id, agent_id)
        return job_id

    def cancel_remote_imaging(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = "cancelled"
        return True

    def update_progress(self, job_id: str, progress: dict) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.progress = progress
        job.status = progress.get("status", job.status)
        return True

    def complete_job(self, job_id: str, result: dict) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = result.get("status", "completed")
        job.result = result
        logger.info("Remote job completed: %s status=%s", job_id, job.status)
        return True

    def get_job_status(self, job_id: str) -> Optional[dict]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "agent_id": job.agent_id,
            "status": job.status,
            "progress": job.progress,
            "result": job.result,
        }

    def get_all_jobs(self) -> list[dict]:
        return [self.get_job_status(jid) for jid in self._jobs if self.get_job_status(jid)]


_remote_service: RemoteService | None = None
_remote_lock = threading.Lock()


def get_remote_service() -> RemoteService:
    global _remote_service
    if _remote_service is not None:
        return _remote_service
    with _remote_lock:
        if _remote_service is None:
            _remote_service = RemoteService()
    return _remote_service
