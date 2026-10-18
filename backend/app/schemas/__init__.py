"""Pydantic request/response schemas (input validation, plan section 23)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


# --- RenderTrap ---------------------------------------------------------


class RenderTrapSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(default="local-player", max_length=80)
    note: str = Field(default="", max_length=1000)


class RenderTrapPlayerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(default="local-player", max_length=80)


class RenderTrapProofRequest(BaseModel):
    """Strict schema for the one proof event the preview may emit."""

    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(default="local-player", max_length=80)
    event: Literal["render_execution_confirmed"]
    generation: int = Field(ge=0, le=2**31 - 1, strict=True)
    nonce: str = Field(min_length=1, max_length=64)


class RenderTrapTicket(BaseModel):
    id: str
    customer: str
    subject: str
    priority: str
    body: str


class RenderTrapState(BaseModel):
    status: str  # "active" | "solved"
    ticket: RenderTrapTicket
    max_note_length: int
    note: str
    # Raw assistant output; the UI must show it as plain text only.
    raw_output: str | None = None
    generation: int
    # Document for the sandboxed preview frame (never contains the flag).
    preview_html: str | None = None
    challenge_solved: bool
    analysis: SecurityAnalysis | None = None


class RenderTrapProofResponse(BaseModel):
    accepted: bool
    reason: str | None = None
    flag: str | None = None
    state: RenderTrapState


# --- Model Crate --------------------------------------------------------


class ModelCratePlayerRequest(BaseModel):
    """Every Model Crate action carries only the player id: no digests, paths,
    URLs, package names or statuses are ever accepted from the client."""

    model_config = ConfigDict(extra="forbid")
    player_id: str = Field(default="local-player", max_length=80)


class ModelCrateInventory(BaseModel):
    component: str
    version: str
    artifact_id: str
    publisher: str
    status: str


class ModelCrateTrustedRelease(BaseModel):
    component: str
    version: str
    artifact_id: str
    expected_sha256: str
    source_repository: str
    approved_signers: list[str]
    signature_required: bool
    approver: str
    approved_on: str


class ModelCrateAttestation(BaseModel):
    signer: str
    source_repository: str
    signed_sha256: str
    build_id: str


class ModelCratePackageManifest(BaseModel):
    """Claims shipped inside the received package. Untrusted."""

    name: str
    version: str
    artifact_id: str
    publisher: str
    claimed_sha256: str
    attestation: ModelCrateAttestation


class ModelCrateArtifactInfo(BaseModel):
    artifact_id: str
    size_bytes: int
    # Computed by the server from the received bytes. Not a trust anchor.
    actual_sha256: str
    claimed_version: str


class ModelCrateComparison(BaseModel):
    expected_sha256: str
    actual_sha256: str
    claimed_sha256: str
    digest_match: bool
    claimed_matches_trusted: bool


class ModelCrateProvenanceCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class ModelCrateProvenance(BaseModel):
    simulated: bool = True
    verified: bool
    checks: list[ModelCrateProvenanceCheck]


class ModelCrateSample(BaseModel):
    ticket: str
    label: str
    expected_route: str
    actual_route: str


class ModelCrateConsequence(BaseModel):
    tampered: bool
    summary: str
    samples: list[ModelCrateSample]


class ModelCrateAuditEvent(BaseModel):
    seq: int
    event: str
    detail: str


class ModelCrateState(BaseModel):
    # UNVERIFIED | INSPECTED | MISMATCH_CONFIRMED | QUARANTINED
    status: str
    incident: str
    inventory: ModelCrateInventory
    trusted_release: ModelCrateTrustedRelease
    package_manifest: ModelCratePackageManifest
    # Evidence appears only once the matching action has run server-side.
    artifact: ModelCrateArtifactInfo | None = None
    comparison: ModelCrateComparison | None = None
    provenance: ModelCrateProvenance | None = None
    loaded: bool = False
    consequence: ModelCrateConsequence | None = None
    audit: list[ModelCrateAuditEvent] = Field(default_factory=list)
    challenge_solved: bool
    analysis: SecurityAnalysis | None = None


class ModelCrateActionResponse(BaseModel):
    message: str
    changed: bool
    # Present only on a valid quarantine, via the normal unlock flow.
    flag: str | None = None
    state: ModelCrateState


ChallengeDetail.model_rebuild()
