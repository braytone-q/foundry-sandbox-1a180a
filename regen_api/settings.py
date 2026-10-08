import os
from dataclasses import dataclass
from pathlib import Path


LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class Settings:
    endpoint: str = "https://veloking45-8432-resource.services.ai.azure.com/api/projects/regen-agentic-ai"
    agent_name: str = "regen"
    agent_version: str = "11"
    image_model: str = "gpt-5-mini"
    question_model: str = "gpt-5-mini"
    search_connection_name: str = "regen-verification-search-mi"
    search_index_name: str = "regen-verification-index"
    database_path: Path = Path("runtime/regen.sqlite3")
    timeout_seconds: float = 90.0
    allowed_hosts: frozenset[str] = LOCAL_HOSTS
    demo_username: str | None = None
    demo_password: str | None = None
    analysis_mode: str = "multiagent"
    activity_model: str = "gpt-5-mini"

    def __post_init__(self):
        if self.analysis_mode not in {"single_agent", "multiagent"}:
            raise ValueError("REGEN_ANALYSIS_MODE must be single_agent or multiagent")

    @classmethod
    def from_env(cls):
        timeout = float(os.getenv("REGEN_REQUEST_TIMEOUT_SECONDS", "90"))
        if not 0 < timeout <= 600:
            raise ValueError("REGEN_REQUEST_TIMEOUT_SECONDS must be between 0 and 600")
        hosts = os.getenv("REGEN_ALLOWED_HOSTS")
        allowed_hosts = frozenset(
            host.strip().lower() for host in hosts.split(",") if host.strip()
        ) if hosts is not None else LOCAL_HOSTS
        if not allowed_hosts:
            raise ValueError("REGEN_ALLOWED_HOSTS must contain at least one hostname")
        username = os.getenv("REGEN_DEMO_USERNAME")
        password = os.getenv("REGEN_DEMO_PASSWORD")
        if bool(username) != bool(password):
            raise ValueError("Set both REGEN_DEMO_USERNAME and REGEN_DEMO_PASSWORD")
        if allowed_hosts - LOCAL_HOSTS and not username:
            raise ValueError("Public hosts require demo username and password")
        return cls(
            endpoint=os.getenv("REGEN_PROJECT_ENDPOINT", cls.endpoint),
            agent_name=os.getenv("REGEN_AGENT_NAME", "regen"),
            agent_version=os.getenv("REGEN_AGENT_VERSION", "11"),
            image_model=os.getenv("REGEN_IMAGE_MODEL", "gpt-5-mini"),
            question_model=os.getenv("REGEN_QUESTION_MODEL", "gpt-5-mini"),
            search_connection_name=os.getenv("REGEN_SEARCH_CONNECTION_NAME", "regen-verification-search-mi"),
            search_index_name=os.getenv("REGEN_SEARCH_INDEX_NAME", "regen-verification-index"),
            database_path=Path(os.getenv("REGEN_DATABASE_PATH", "runtime/regen.sqlite3")),
            timeout_seconds=timeout,
            allowed_hosts=allowed_hosts,
            demo_username=username,
            demo_password=password,
            analysis_mode=os.getenv("REGEN_ANALYSIS_MODE", "multiagent"),
            activity_model=os.getenv("REGEN_ACTIVITY_MODEL", "gpt-5-mini"),
        )
