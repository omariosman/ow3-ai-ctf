"""Model Crate challenge-specific endpoints.

    GET  /api/challenges/model-crate/state       inventory, trusted record, evidence
    POST /api/challenges/model-crate/inspect     hash the received artifact
    POST /api/challenges/model-crate/compare     compare with the trusted digest
    POST /api/challenges/model-crate/provenance  (simulated) provenance check
    POST /api/challenges/model-crate/load        simulated load (refused once failed)
    POST /api/challenges/model-crate/quarantine  reject the artifact -> solve
    POST /api/challenges/model-crate/reset       restore initial state

Every action body carries only ``player_id``. The server hashes the fixture
bytes, reads the trusted record from its own files, and decides each state
transition; the client can supply no digest, path, URL or status. The flag is
returned only by a valid ``quarantine`` (same unlock + flag-store flow as the
other challenges) and is never part of ``/state``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..challenges.model_crate import SLUG
from ..challenges.model_crate import state as mc_state
from ..challenges.model_crate import verifier
from ..config import get_settings
from ..database import get_db
from ..models import ModelCrateSession
from ..rate_limit import build_limiter
from ..schemas import (
    ModelCrateActionResponse,
    ModelCrateArtifactInfo,
    ModelCrateAttestation,
    ModelCrateAuditEvent,
    ModelCrateComparison,
    ModelCrateConsequence,
    ModelCrateInventory,
    ModelCratePackageManifest,
    ModelCratePlayerRequest,
    ModelCrateProvenance,
    ModelCrateProvenanceCheck,
    ModelCrateSample,
    ModelCrateState,
    ModelCrateTrustedRelease,
    SecurityAnalysis,
)
from ..services import flag_store, progress

router = APIRouter(prefix="/api/challenges/model-crate", tags=["model-crate"])
logger = logging.getLogger("ctf.model_crate")
settings = get_settings()

_rate_limiter = build_limiter(settings.predict_rate_limit)

_INCIDENT = (
    "Northstar AI's ticket classifier uses a third-party adapter. Release "
    "engineering noticed the artifact in the inventory is still UNVERIFIED and "
    "may have been replaced after approval, while the bundled manifest still "
    "looks plausible. Decide whether it is safe to load."
)

_ANALYSIS = SecurityAnalysis(
    owasp="LLM03:2025",
    root_cause=(
        "Supply chain trust placed in a filename, version and bundled manifest "
        "instead of an independently verified digest and provenance"
    ),
    what_happened=[
        "The received adapter had the right name and version, and its own manifest claimed the right digest.",
        "A digest computed from the received bytes did not match the independent release record.",
        "The provenance attestation did not match the approved source or the received bytes.",
        "A compromised component can change AI behaviour without touching the application's source code.",
    ],
    broken=(
        "artifact = find_by_name('northstar-ticket-adapter', '1.4.2')\n"
        "load(artifact)   # trusts filename + version (pseudocode)"
    ),
    secure=(
        "trusted = read_release_record()          # separate, trusted source\n"
        "actual = sha256(artifact_bytes)          # computed server-side\n"
        "if actual != trusted.expected_sha256 or not verify_provenance(artifact, trusted):\n"
        "    quarantine(artifact); audit(); raise Rejected   # fail closed\n"
        "load(artifact)                           # only after both checks pass (pseudocode)"
    ),
)


def _challenge_row(db: Session):
    row = progress.get_challenge_row(db, SLUG)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return row


def _check_player_id(player_id: str) -> None:
    if not player_id or len(player_id) > 80:
        raise HTTPException(status_code=422, detail="Invalid player id")


def _rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")


def _build_state(row: ModelCrateSession, unlocked: bool) -> ModelCrateState:
    trusted = verifier.load_trusted_release()
    artifact = verifier.load_received_artifact()
    manifest = artifact.manifest
    att = manifest.attestation

    inspected = row.status != mc_state.UNVERIFIED
    artifact_info = None
    if inspected:
        artifact_info = ModelCrateArtifactInfo(
            artifact_id=artifact.artifact_id,
            size_bytes=artifact.size_bytes,
            actual_sha256=verifier.sha256_hex(artifact.data),
            claimed_version=manifest.version,
        )

    comparison = None
    if row.digest_match is not None:
        c = verifier.compare_digest(artifact, trusted)
        comparison = ModelCrateComparison(
            expected_sha256=c.expected_sha256,
            actual_sha256=c.actual_sha256,
            claimed_sha256=c.claimed_sha256,
            digest_match=c.digest_match,
            claimed_matches_trusted=c.claimed_matches_trusted,
        )

    provenance = None
    if row.provenance_result is not None:
        p = verifier.verify_provenance(artifact, trusted)
        provenance = ModelCrateProvenance(
            verified=p.verified,
            checks=[
                ModelCrateProvenanceCheck(name=c.name, passed=c.passed, detail=c.detail)
                for c in p.checks
            ],
        )

    consequence = None
    sim = mc_state.consequence_for(row)
    if sim is not None:
        consequence = ModelCrateConsequence(
            tampered=sim.tampered,
            summary=sim.summary,
            samples=[
                ModelCrateSample(
                    ticket=s.ticket,
                    label=s.label,
                    expected_route=s.expected_route,
                    actual_route=s.actual_route,
                )
                for s in sim.samples
            ],
        )

    return ModelCrateState(
        status=row.status,
        incident=_INCIDENT,
        inventory=ModelCrateInventory(
            component=trusted.component,
            version=manifest.version,
            artifact_id=artifact.artifact_id,
            publisher=manifest.publisher,
            status=row.status,
        ),
        trusted_release=ModelCrateTrustedRelease(
            component=trusted.component,
            version=trusted.version,
            artifact_id=trusted.artifact_id,
            expected_sha256=trusted.expected_sha256,
            source_repository=trusted.source_repository,
            approved_signers=list(trusted.approved_signers),
            signature_required=trusted.signature_required,
            approver=trusted.approver,
            approved_on=trusted.approved_on,
        ),
        package_manifest=ModelCratePackageManifest(
            name=manifest.name,
            version=manifest.version,
            artifact_id=manifest.artifact_id,
            publisher=manifest.publisher,
            claimed_sha256=manifest.claimed_sha256,
            attestation=ModelCrateAttestation(
                signer=att.signer,
                source_repository=att.source_repository,
                signed_sha256=att.signed_sha256,
                build_id=att.build_id,
            ),
        ),
        artifact=artifact_info,
        comparison=comparison,
        provenance=provenance,
        loaded=row.loaded,
        consequence=consequence,
        audit=[ModelCrateAuditEvent(**e) for e in mc_state.audit_events(row)],
        challenge_solved=unlocked,
        analysis=_ANALYSIS if unlocked and row.status == mc_state.QUARANTINED else None,
    )


def _respond(
    db: Session,
    player_id: str,
    challenge_id: int,
    row: ModelCrateSession,
    message: str,
    changed: bool,
    flag: str | None = None,
) -> ModelCrateActionResponse:
    return ModelCrateActionResponse(
        message=message,
        changed=changed,
        flag=flag,
        state=_build_state(row, progress.is_unlocked(db, player_id, challenge_id)),
    )


@router.get("/state", response_model=ModelCrateState)
def get_state(
    player_id: str = "local-player", db: Session = Depends(get_db)
) -> ModelCrateState:
    _check_player_id(player_id)
    row = _challenge_row(db)
    progress.ensure_player(db, player_id)
    sess = mc_state.ensure_session(db, player_id)
    db.commit()
    return _build_state(sess, progress.is_unlocked(db, player_id, row.id))


def _run_action(
    request: Request,
    payload: ModelCratePlayerRequest,
    db: Session,
    action: str,
    fn,
    done: str,
    already: str,
) -> ModelCrateActionResponse:
    _rate_limit(request)
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    try:
        sess, changed = fn(db, payload.player_id)
    except mc_state.InvalidTransition as exc:
        db.commit()  # keep any audit entry (e.g. a blocked load)
        logger.info("model-crate %s player=%s rejected", action, payload.player_id)
        raise HTTPException(status_code=409, detail=str(exc))
    flag = None
    if action == "quarantine" and sess.status == mc_state.QUARANTINED:
        progress.mark_unlocked(db, payload.player_id, row.id)
        flag = flag_store.load_flag(SLUG)
    db.commit()
    logger.info(
        "model-crate %s player=%s changed=%s status=%s",
        action,
        payload.player_id,
        changed,
        sess.status,
    )
    return _respond(
        db, payload.player_id, row.id, sess, done if changed else already, changed, flag
    )


@router.post("/inspect", response_model=ModelCrateActionResponse)
def inspect(
    request: Request, payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateActionResponse:
    return _run_action(
        request, payload, db, "inspect", mc_state.inspect,
        "Artifact inspected. Its digest was computed from the received bytes.",
        "Artifact already inspected.",
    )


@router.post("/compare", response_model=ModelCrateActionResponse)
def compare(
    request: Request, payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateActionResponse:
    return _run_action(
        request, payload, db, "compare", mc_state.compare,
        "Compared the received digest with the trusted release record.",
        "Already compared.",
    )


@router.post("/provenance", response_model=ModelCrateActionResponse)
def provenance(
    request: Request, payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateActionResponse:
    return _run_action(
        request, payload, db, "provenance", mc_state.check_provenance,
        "Provenance checked (simulated).",
        "Provenance already checked.",
    )


@router.post("/load", response_model=ModelCrateActionResponse)
def load(
    request: Request, payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateActionResponse:
    return _run_action(
        request, payload, db, "load", mc_state.load_artifact,
        "Adapter loaded (simulated). Nothing from the artifact was executed.",
        "Adapter already loaded.",
    )


@router.post("/quarantine", response_model=ModelCrateActionResponse)
def quarantine(
    request: Request, payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateActionResponse:
    return _run_action(
        request, payload, db, "quarantine", mc_state.quarantine,
        "Artifact rejected: digest mismatch. Quarantined; it will not be loaded.",
        "Artifact already quarantined.",
    )


@router.post("/reset", response_model=ModelCrateState)
def reset(
    payload: ModelCratePlayerRequest, db: Session = Depends(get_db)
) -> ModelCrateState:
    """Reset this player's Model Crate state. Other challenges and any recorded solve are untouched."""
    row = _challenge_row(db)
    progress.ensure_player(db, payload.player_id)
    sess = mc_state.reset_player(db, payload.player_id)
    db.commit()
    logger.info("model-crate reset player=%s", payload.player_id)
    return _build_state(sess, progress.is_unlocked(db, payload.player_id, row.id))
