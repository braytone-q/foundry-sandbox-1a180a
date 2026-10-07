from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Recommendation = Literal["NEEDS_CLARIFICATION", "READY_FOR_HUMAN_REVIEW", "FLAG_FOR_REVIEW"]
HumanAction = Literal["APPROVE", "REJECT", "REQUEST_CLARIFICATION"]
ReviewStatus = Literal["PENDING_REVIEW", "CLARIFICATION_REQUESTED", "APPROVED", "REJECTED"]
AttemptState = Literal["RUNNING", "SUCCEEDED", "FAILED"]
Description = Annotated[str, StringConstraints(min_length=1, max_length=16000)]
Version = Annotated[int, Field(ge=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Analysis(StrictModel):
    activity_type: str | None
    quantity: int | float | None
    species: str | None
    species_category: str | None
    activity_date: str | None
    location: str | None
    community_group: str | None
    evidence_reported: list[str]
    evidence_received: list[str]
    missing_information: list[str]
    inconsistencies: list[str]
    recommendation: Recommendation
    reason: str
    clarification_question: str | None

    @model_validator(mode="after")
    def coherent_recommendation(self):
        if not self.reason.strip():
            raise ValueError("A reason is required")
        if self.recommendation == "READY_FOR_HUMAN_REVIEW" and (
            self.missing_information or self.inconsistencies or self.clarification_question is not None
        ):
            raise ValueError("A ready recommendation cannot contain unresolved findings")
        if self.recommendation == "NEEDS_CLARIFICATION" and (
            not self.missing_information or self.inconsistencies
            or not self.clarification_question or not self.clarification_question.strip()
        ):
            raise ValueError("Clarification requires missing information and a question")
        return self


class SubmissionInput(StrictModel):
    description: Description

    @model_validator(mode="after")
    def meaningful_description(self):
        if not self.description.strip():
            raise ValueError("Describe the activity")
        return self


class RetryInput(StrictModel):
    expected_version: Version


class RevisionInput(SubmissionInput):
    expected_version: Version


class ReviewInput(RetryInput):
    action: HumanAction
    reviewer_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    notes: Annotated[str, StringConstraints(min_length=1, max_length=4000)]

    @model_validator(mode="after")
    def meaningful_review(self):
        if not self.reviewer_name.strip() or not self.notes.strip():
            raise ValueError("Reviewer name and notes are required")
        return self


class Citation(StrictModel):
    title: str
    url: str


class ImageComparison(StrictModel):
    image_id: str
    filename: str
    image_number: int
    verdict: Literal["SUPPORTS", "UNRELATED", "CONTRADICTS", "UNCLEAR"]
    visible_content: str
    explanation: str


class ImageAssessment(StrictModel):
    overall: Literal["SUPPORTS", "MISMATCH", "INCONCLUSIVE"]
    model: str
    response_id: str | None
    images: list[ImageComparison]


class Attempt(StrictModel):
    id: str
    revision: int
    state: AttemptState
    started_at: str
    finished_at: str | None
    agent_name: str
    agent_version: str
    response_id: str | None
    analysis: Analysis | None
    failure_code: str | None
    failure_message: str | None
    citations: list[Citation]
    image_ids: list[str] = Field(default_factory=list)
    image_assessment: ImageAssessment | None = None


class Revision(StrictModel):
    revision: int
    description: str
    created_at: str
    image_ids: list[str] = Field(default_factory=list)


class ImageEvidence(StrictModel):
    id: str
    filename: str
    media_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    created_at: str
    url: str


class ReviewEvent(StrictModel):
    id: str
    revision: int
    attempt_id: str
    action: HumanAction
    reviewer_name: str
    notes: str
    created_at: str


class SubmissionRecord(StrictModel):
    id: str
    version: int
    current_revision: int
    description: str
    review_status: ReviewStatus
    created_at: str
    updated_at: str
    latest_attempt: Attempt | None
    revisions: list[Revision]
    attempts: list[Attempt]
    reviews: list[ReviewEvent]
    images: list[ImageEvidence] = Field(default_factory=list)


class SubmissionPage(StrictModel):
    items: list[SubmissionRecord]
    total: int
    limit: int
    offset: int
