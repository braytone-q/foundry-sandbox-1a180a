"""Controlled browser-QA server. Run only with --factory tests.browser_fixture:create_app."""
from dataclasses import replace
from pathlib import Path

from regen_api.foundry import AnalysisFailure
from regen_api.main import create_app as real_app
from regen_api.settings import Settings
from tests.conftest import ControlledGateway


class BrowserGateway(ControlledGateway):
    def analyze(self, description, images=None, on_image_assessment=None):
        if "QA failure" in description:
            raise AnalysisFailure("TIMEOUT", "Controlled QA timeout. Source is saved; retry analysis.")
        from tests.test_contract import payload
        self.data = payload()
        if "QA clarification" in description:
            self.data.update(recommendation="NEEDS_CLARIFICATION", missing_information=["precise location"],
                             location=None, clarification_question="Where did the planting take place?")
        return super().analyze(description, images, on_image_assessment)


def create_app():
    return real_app(replace(Settings(analysis_mode="single_agent"), database_path=Path("runtime/browser-qa.sqlite3")), BrowserGateway())
