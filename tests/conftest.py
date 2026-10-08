from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from regen_api.foundry import parse_response
from regen_api.schemas import Analysis
from regen_api.settings import Settings
from tests.test_contract import payload, response


class ControlledGateway:
    def __init__(self):
        self.data = payload()
        self.failure = None
        self.descriptions = []
        self.image_batches = []

    def analyze(self, description, images=None, on_image_assessment=None):
        self.descriptions.append(description)
        self.image_batches.append(images or [])
        if self.failure:
            raise self.failure
        return parse_response(response(self.data), [f"Image {i + 1}: {image['filename']}" for i, image in enumerate(images or [])])

    def close(self):
        pass


@pytest.fixture
def app_bundle(tmp_path):
    from regen_api.main import create_app
    settings = replace(Settings(analysis_mode="single_agent"), database_path=tmp_path / "test.sqlite3")
    gateway = ControlledGateway()
    app = create_app(settings, gateway)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, app, gateway, settings


@pytest.fixture
def client(app_bundle):
    return app_bundle[0]
