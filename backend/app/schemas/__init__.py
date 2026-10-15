"""Pydantic request/response schemas (input validation, plan section 23)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChallengeSummary(BaseModel):
    slug: str
    title: str
    category: str
    difficulty: str
    points: int
    author: str
    solved: bool = False


class ChallengeDetail(ChallengeSummary):
    description: str
    learning_objectives: list[str] = Field(default_factory=list)
    hints: list["Hint"] = Field(default_factory=list)
    # True once the in-challenge solve condition has been met and the flag is
    # available to retrieve. Never includes the flag itself.
    unlocked: bool = False


class Hint(BaseModel):
    order: int
    cost: int
    text: str


class SubmitRequest(BaseModel):
    player_id: str = Field(default="local-player", max_length=80)
    flag: str = Field(min_length=1, max_length=300)


class SubmitResponse(BaseModel):
    correct: bool
    solved: bool
    message: str


class PredictRequest(BaseModel):
    player_id: str = Field(default="local-player", max_length=80)
    text: str = Field(min_length=0, max_length=2000)


class PredictResponse(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]
    request_number: int
    # Populated only once the deterministic solve condition is met. This is how
    # a solved player receives the flag (plan section 15).
    solved_condition: bool = False
    flag: str | None = None
    note: str | None = None


# ---- Release Roulette ----


class ReleaseRouletteChatRequest(BaseModel):
    player_id: str = Field(default="local-player", max_length=80)
    message: str = Field(min_length=0, max_length=1000)


class ReleaseRoulettePlayerRequest(BaseModel):
    player_id: str = Field(default="local-player", max_length=80)


class ReleaseView(BaseModel):
    release_id: str
    project: str
    version: str
    environment: str
    status: str
    protected: bool
    last_actor: str | None = None


class AuditEvent(BaseModel):
    request_id: str
    tool: str
    release_id: str | None = None
    actor: str
    ok: bool
    transition: str | None = None
    timestamp: str


class ToolCall(BaseModel):
    tool: str
    release_id: str | None = None
    ok: bool
    transition: str | None = None


class SecurityAnalysis(BaseModel):
    owasp: str
    root_cause: str
    what_happened: list[str]
    broken: str
    secure: str


class ReleaseRouletteState(BaseModel):
    status: str  # "active" | "solved"
    target_release: str
    releases: list[ReleaseView]
    audit: list[AuditEvent]
    challenge_solved: bool
    # Present only once the player has met the solve condition.
    analysis: SecurityAnalysis | None = None


class ReleaseRouletteChatResponse(BaseModel):
    request_id: str
    reply: str
    tool_calls: list[ToolCall]
    state: ReleaseRouletteState
    solved_condition: bool = False
    flag: str | None = None
    note: str | None = None


ChallengeDetail.model_rebuild()
