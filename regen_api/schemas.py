from typing import Annotated, Literal
from datetime import datetime, timezone

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


class DeviceLocation(StrictModel):
    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]
    accuracy_m: Annotated[float, Field(ge=0)]
    captured_at: str
    source: Literal["browser_geolocation"]

    @model_validator(mode="after")
    def aware_capture_time(self):
        captured = datetime.fromisoformat(self.captured_at)
        if captured.utcoffset() is None:
            raise ValueError("Location capture time must include a timezone")
        return self


class SubmissionInput(StrictModel):
    description: Description
    device_location: DeviceLocation

    @model_validator(mode="after")
    def meaningful_description(self):
        if not self.description.strip():
            raise ValueError("Describe the activity")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(self.device_location.captured_at)).total_seconds()
        if not -30 <= age <= 300:
            raise ValueError("Capture a fresh device location before submitting")
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


QuestionText = Annotated[str, StringConstraints(min_length=1, max_length=4000)]
ConversationText = Annotated[str, StringConstraints(min_length=1, max_length=12000)]


class QuestionMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: ConversationText

    @model_validator(mode="after")
    def meaningful_content(self):
        if not self.content.strip():
            raise ValueError("Conversation messages cannot be blank")
        return self


class QuestionInput(StrictModel):
    question: QuestionText
    history: Annotated[list[QuestionMessage], Field(max_length=12)] = Field(default_factory=list)

    @model_validator(mode="after")
    def bounded_conversation(self):
        if not self.question.strip() or len(self.history) % 2:
            raise ValueError("Supply a question and complete conversation pairs")
        if any(message.role != ("user" if index % 2 == 0 else "assistant")
               for index, message in enumerate(self.history)):
            raise ValueError("Conversation must alternate user and assistant")
        if sum(len(message.content) for message in self.history) > 24000:
            raise ValueError("Conversation context is too long")
        return self


class QuestionAnswer(StrictModel):
    answer: ConversationText
    response_id: str | None
    citations: list[Citation]
    knowledge_searched: bool

    @model_validator(mode="after")
    def meaningful_answer(self):
        if not self.answer.strip():
            raise ValueError("An answer cannot be blank")
        return self


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
    device_location: DeviceLocation | None = None


class Revision(StrictModel):
    revision: int
    description: str
    created_at: str
    image_ids: list[str] = Field(default_factory=list)
    device_location: DeviceLocation | None = None


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
    device_location: DeviceLocation | None = None


class SubmissionPage(StrictModel):
    items: list[SubmissionRecord]
    total: int
    limit: int
    offset: int
