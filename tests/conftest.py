from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from regen_api.foundry import AnalysisResult
from regen_api.schemas import Analysis
from regen_api.settings import Settings
from tests.test_contract import payload


class ControlledGateway:
    def __init__(self):
        self.data = payload()
        self.failure = None
        self.descriptions = []

    def analyze(self, description):
        self.descriptions.append(description)
        if self.failure:
            raise self.failure
        return AnalysisResult(Analysis.model_validate(self.data), "controlled-response")

    def close(self):
        pass


@pytest.fixture
def app_bundle(tmp_path):
    from regen_api.main import create_app
    settings = replace(Settings(), database_path=tmp_path / "test.sqlite3")
    gateway = ControlledGateway()
    app = create_app(settings, gateway)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, app, gateway, settings


@pytest.fixture
def client(app_bundle):
    return app_bundle[0]
