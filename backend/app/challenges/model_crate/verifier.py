"""Server-side artifact verification for Model Crate.

Two independent sources are kept strictly apart:

* the **trusted release record** (``fixtures/trusted/trusted_release.json``),
  authored by the release team and never derived from the received artifact;
* the **received artifact** (``fixtures/artifacts/``): its bytes and the
  manifest shipped inside it, both untrusted.

The artifact is only ever *read as bytes and hashed*. It is never parsed as
code, imported, executed, or passed to a loader, and nothing inside it (or its
manifest) can select a path, URL, command or module: every path below is a
fixed constant.

The SHA-256 digest comparison is real. The provenance/signature check is a
*simulation*: it compares recorded attestation fields against the trusted
record and does no cryptography. The API labels it as such.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_TRUSTED_PATH = _FIXTURES / "trusted" / "trusted_release.json"
_ARTIFACT_PATH = _FIXTURES / "artifacts" / "adapter-1.4.2.pkg"
_MANIFEST_PATH = _FIXTURES / "artifacts" / "package-manifest.json"

_MAX_FIELD = 200  # untrusted manifest strings are clipped before use


@dataclass(frozen=True)
class TrustedRelease:
    component: str
    version: str
    artifact_id: str
    expected_sha256: str
    source_repository: str
    approved_signers: tuple[str, ...]
    signature_required: bool
    approver: str
    approved_on: str


@dataclass(frozen=True)
class Attestation:
    signer: str
    source_repository: str
    signed_sha256: str
    build_id: str


@dataclass(frozen=True)
class PackageManifest:
    """Claims shipped with the received package. Untrusted."""

    name: str
    version: str
    artifact_id: str
    publisher: str
    claimed_sha256: str
    attestation: Attestation


@dataclass(frozen=True)
class ReceivedArtifact:
    artifact_id: str
    data: bytes
    manifest: PackageManifest

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class Comparison:
    expected_sha256: str
    actual_sha256: str
    claimed_sha256: str
    digest_match: bool
    claimed_matches_trusted: bool


@dataclass(frozen=True)
class ProvenanceCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ProvenanceResult:
    verified: bool
    checks: tuple[ProvenanceCheck, ...]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clip(value: object) -> str:
    return value[:_MAX_FIELD] if isinstance(value, str) else ""


def load_trusted_release(path: Path = _TRUSTED_PATH) -> TrustedRelease:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return TrustedRelease(
        component=raw["component"],
        version=raw["version"],
        artifact_id=raw["artifact_id"],
        expected_sha256=raw["expected_sha256"],
        source_repository=raw["source_repository"],
        approved_signers=tuple(raw["approved_signers"]),
        signature_required=bool(raw["signature_required"]),
        approver=raw["approver"],
        approved_on=raw["approved_on"],
    )


def parse_manifest(raw: object) -> PackageManifest:
    """Tolerantly read the untrusted manifest; anything odd becomes ''."""
    d = raw if isinstance(raw, dict) else {}
    att = d.get("attestation")
    a = att if isinstance(att, dict) else {}
    return PackageManifest(
        name=_clip(d.get("name")),
        version=_clip(d.get("version")),
        artifact_id=_clip(d.get("artifact_id")),
        publisher=_clip(d.get("publisher")),
        claimed_sha256=_clip(d.get("claimed_sha256")),
        attestation=Attestation(
            signer=_clip(a.get("signer")),
            source_repository=_clip(a.get("source_repository")),
            signed_sha256=_clip(a.get("signed_sha256")),
            build_id=_clip(a.get("build_id")),
        ),
    )


def load_received_artifact(
    artifact_path: Path = _ARTIFACT_PATH, manifest_path: Path = _MANIFEST_PATH
) -> ReceivedArtifact:
    """Read the received artifact's raw bytes and its (untrusted) manifest."""
    manifest = parse_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    return ReceivedArtifact(
        artifact_id=artifact_path.name,
        data=artifact_path.read_bytes(),
        manifest=manifest,
    )


def compare_digest(artifact: ReceivedArtifact, trusted: TrustedRelease) -> Comparison:
    """Hash the received bytes and compare with the TRUSTED expected digest.

    The manifest's own ``claimed_sha256`` is reported for the player but is
    never used as the reference: the expected value always comes from the
    trusted release record.
    """
    actual = sha256_hex(artifact.data)
    claimed = artifact.manifest.claimed_sha256
    return Comparison(
        expected_sha256=trusted.expected_sha256,
        actual_sha256=actual,
        claimed_sha256=claimed,
        digest_match=actual == trusted.expected_sha256,
        claimed_matches_trusted=claimed == trusted.expected_sha256,
    )


def verify_provenance(
    artifact: ReceivedArtifact, trusted: TrustedRelease
) -> ProvenanceResult:
    """SIMULATED provenance check (no real cryptography).

    Fails closed: every check must pass. A missing/empty attestation fails.
    """
    att = artifact.manifest.attestation
    actual = sha256_hex(artifact.data)
    checks = (
        ProvenanceCheck(
            "Signer is an approved release key",
            bool(att.signer) and att.signer in trusted.approved_signers,
            f"attested signer '{att.signer or '(none)'}'; approved: "
            + ", ".join(trusted.approved_signers),
        ),
        ProvenanceCheck(
            "Built from the approved source repository",
            bool(att.source_repository)
            and att.source_repository == trusted.source_repository,
            f"attested '{att.source_repository or '(none)'}'; approved "
            f"'{trusted.source_repository}'",
        ),
        ProvenanceCheck(
            "Attestation covers the bytes actually received",
            bool(att.signed_sha256) and att.signed_sha256 == actual,
            "the attestation vouches for a digest; it must equal the digest "
            "computed from the received artifact",
        ),
    )
    return ProvenanceResult(verified=all(c.passed for c in checks), checks=checks)


def is_verified(comparison: Comparison, provenance: ProvenanceResult | None) -> bool:
    """A component may be trusted only if digest AND required provenance pass."""
    return comparison.digest_match and bool(provenance and provenance.verified)
