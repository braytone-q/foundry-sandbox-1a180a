import json
import threading
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from pydantic import ValidationError

from .schemas import Analysis, Citation
from .settings import Settings


class AnalysisFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AnalysisResult:
    analysis: Analysis
    response_id: str | None = None
    citations: list[Citation] = field(default_factory=list)


def parse_response(response) -> AnalysisResult:
    if response.status != "completed":
        raise AnalysisFailure("UPSTREAM_ERROR", "The agent did not complete its analysis. Retry analysis.")
    results = [item for item in response.output if item.type == "azure_ai_search_call_output"]
    if not results or any(getattr(item, "error", None) or getattr(item, "status", None) in
                          {"failed", "incomplete", "cancelled"} for item in results):
        raise AnalysisFailure("RETRIEVAL_MISSING", "Approved-rule retrieval did not complete. Retry analysis.")
    messages = [item for item in response.output if item.type == "message" and
                getattr(item, "role", "assistant") == "assistant"]
    if len(messages) != 1:
        raise AnalysisFailure("INVALID_ANALYSIS", "The agent returned an invalid analysis. Retry analysis.")
    content = [part for part in messages[0].content if part.type == "output_text"]
    try:
        analysis = Analysis.model_validate(json.loads("".join(part.text for part in content)))
    except (ValueError, TypeError, ValidationError) as exc:
        raise AnalysisFailure("INVALID_ANALYSIS", "The agent returned an invalid analysis. Retry analysis.") from exc
    citations = []
    seen = set()
    for part in content:
        for annotation in getattr(part, "annotations", []) or []:
            if getattr(annotation, "type", None) != "url_citation":
                continue
            url = getattr(annotation, "url", "") or ""
            try:
                parsed = urlsplit(url)
                safe = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username
            except ValueError:
                safe = False
            if safe and url not in seen:
                citations.append(Citation(title=getattr(annotation, "title", None) or "Retrieved source", url=url))
                seen.add(url)
    return AnalysisResult(analysis, getattr(response, "id", None), citations)


def safe_failure(exc: Exception) -> AnalysisFailure:
    from azure.core.exceptions import ClientAuthenticationError
    from openai import APITimeoutError, AuthenticationError, PermissionDeniedError

    if isinstance(exc, AnalysisFailure):
        return exc
    if isinstance(exc, (ClientAuthenticationError, AuthenticationError)):
        return AnalysisFailure("AUTHENTICATION", "Azure sign-in failed. Sign in with Azure CLI, then retry analysis.")
    if isinstance(exc, (TimeoutError, APITimeoutError)):
        return AnalysisFailure("TIMEOUT", "Analysis timed out. Your submission is saved; retry analysis.")
    if isinstance(exc, PermissionDeniedError) or getattr(exc, "status_code", None) == 403 or (
        getattr(exc, "status_code", None) == 400 and "access denied" in str(exc).lower()
    ):
        return AnalysisFailure("ACCESS_DENIED", "The agent cannot access its knowledge source. Check Azure permissions, then retry.")
    return AnalysisFailure("UPSTREAM_ERROR", "The agent service could not complete analysis. Your submission is saved; retry analysis.")


class FoundryGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._credential = self._project = self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                from azure.ai.projects import AIProjectClient
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
                self._project = AIProjectClient(endpoint=self.settings.endpoint, credential=self._credential)
                self._client = self._project.get_openai_client(
                    timeout=self.settings.timeout_seconds, max_retries=0,
                )
        return self._client

    def analyze(self, description: str) -> AnalysisResult:
        try:
            response = self._get_client().responses.create(
                input=[{"role": "user", "content": description}],
                extra_body={"agent_reference": {"name": self.settings.agent_name,
                    "version": self.settings.agent_version, "type": "agent_reference"}},
            )
            return parse_response(response)
        except Exception as exc:
            raise safe_failure(exc) from exc

    def close(self):
        for resource in (self._client, self._project, self._credential):
            if resource is not None:
                resource.close()
        self._client = self._project = self._credential = None
