import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    endpoint: str = "https://veloking45-8432-resource.services.ai.azure.com/api/projects/regen-agentic-ai"
    agent_name: str = "regen"
    agent_version: str = "11"
    image_model: str = "gpt-5-mini"
    database_path: Path = Path("runtime/regen.sqlite3")
    timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls):
        timeout = float(os.getenv("REGEN_REQUEST_TIMEOUT_SECONDS", "90"))
        if not 0 < timeout <= 600:
            raise ValueError("REGEN_REQUEST_TIMEOUT_SECONDS must be between 0 and 600")
        return cls(
            endpoint=os.getenv("REGEN_PROJECT_ENDPOINT", cls.endpoint),
            agent_name=os.getenv("REGEN_AGENT_NAME", "regen"),
            agent_version=os.getenv("REGEN_AGENT_VERSION", "11"),
            image_model=os.getenv("REGEN_IMAGE_MODEL", "gpt-5-mini"),
            database_path=Path(os.getenv("REGEN_DATABASE_PATH", "runtime/regen.sqlite3")),
            timeout_seconds=timeout,
        )
