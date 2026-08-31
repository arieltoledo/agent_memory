"""Executable schema for Memory Agent test fixtures.

The `expected:` block of every fixture is the FROZEN contract. It is the
interface an implementation must satisfy, and it is never relaxed to make
code pass. If a fixture and an authoritative source disagree, the harness
flags the case as TEST_SPEC_CONFLICT and stops it for review.

Probabilistic components are driven by `forced_*_output` / `injected_failures`
so the deterministic kernel can be exercised without any real LLM.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.enums import (
    ArchitecturalOutcome,
    AuditDecision,
    DetectionLayer,
    RestrictionLevel,
    SecurityOutcome,
)


# ---------------------------------------------------------------------------
# Frozen expectation block
# ---------------------------------------------------------------------------

class ExpectedDetection(BaseModel):
    """Detection-layer telemetry, kept independent so a test is never a bare
    boolean. `security_outcome` and `architectural_outcome` are asserted
    separately: e.g. an unsafe commit may be `PASS` on security but `DEGRADED`
    on architecture if it was stopped too late (policy bypass)."""

    model_config = ConfigDict(extra="forbid")

    security_outcome: SecurityOutcome | None = None
    architectural_outcome: ArchitecturalOutcome | None = None
    # Kept as str (not the enum) so a TEST_SPEC_CONFLICT case that references a
    # layer not present in the authoritative DetectionLayer enum (e.g. the
    # traceability table's COMMIT_ENGINE) can be captured for review.
    expected_detection_layer: str | None = None
    actual_detection_layer: str | None = None
    policy_bypass: bool | None = None

    result: str | None = None
    error_code: str | None = None
    state: dict[str, Any] | None = None
    post_state: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Forced / injected overrides for probabilistic components
# ---------------------------------------------------------------------------

class ForcedOutput(BaseModel):
    # Analyzer
    semantic_type: str | None = None
    sensitivity: str | None = None
    persistence_intent: str | None = None
    temporal_scope: str | None = None
    domain_hint: str | None = None
    # Guard (independent deterministic barrier)
    restriction: RestrictionLevel | None = None
    # Segmenter
    segments: list[dict[str, Any]] | None = None
    # Generator -> proposed DraftPatch
    operations: list[dict[str, Any]] | None = None
    # Auditor
    auditor_decision: AuditDecision | None = None
    # Mount
    mount_decision: str | None = None
    # Generator textual output (for Output Gate path)
    output_text: str | None = None


class InjectedFailures(BaseModel):
    """Failures injected into deterministic components to prove fail-closed
    behavior and audit binding. These are orthogonal to the LLM fakes."""

    model_config = ConfigDict(extra="forbid")

    auditor_unavailable: bool = False
    commit_without_audit: bool = False
    patch_substituted_after_audit: bool = False
    commit_replayed: bool = False
    purge_partial_failure: bool = False
    policy_change_after_audit: bool = False
    purge_during_generation: bool = False
    stale_base_revision: bool = False
    target_missing: bool = False
    target_not_active: bool = False
    invalid_evidence: bool = False
    cross_scope_evidence: bool = False


# ---------------------------------------------------------------------------
# Initial state + input
# ---------------------------------------------------------------------------

class InitialState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch: str = "branch-a"
    active_branch: str | None = None
    revision: int = 0
    policy_version: int = 1
    core_version: int = 1
    # semantic_key -> {value, status, domain, lifetime, valid_until, ...}
    records: dict[str, dict[str, Any]] = Field(default_factory=dict)
    commits: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)
    mount_policies: dict[str, dict[str, Any]] = Field(default_factory=dict)
    leases: list[dict[str, Any]] = Field(default_factory=list)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = None
    text_spans: list[dict[str, Any]] | None = None
    requested_scope: str | None = None
    requested_memory_keys: list[str] | None = None
    query: str | None = None


# ---------------------------------------------------------------------------
# Root fixture spec
# ---------------------------------------------------------------------------

class FixtureSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["GOLDEN", "ADVERSARIAL", "UNIT"]
    source: str = "unknown"  # doc + section reference for TEST_SPEC_CONFLICT lookup
    summary: str = ""

    initial_state: InitialState = Field(default_factory=InitialState)
    input: Input = Field(default_factory=Input)

    forced_model_output: ForcedOutput = Field(default_factory=ForcedOutput)
    forced_segmenter_output: ForcedOutput = Field(default_factory=ForcedOutput)
    forced_auditor_output: ForcedOutput = Field(default_factory=ForcedOutput)

    injected_failures: InjectedFailures = Field(default_factory=InjectedFailures)

    expected: ExpectedDetection

    # Execution control
    status: Literal["ACTIVE", "NOT_IMPLEMENTED", "TEST_SPEC_CONFLICT"] = "ACTIVE"
    notes: str = ""


class FixtureBundle(BaseModel):
    """A set of fixtures sharing a single source document."""

    model_config = ConfigDict(extra="forbid")

    source: str
    fixtures: dict[str, FixtureSpec]


class UnfrozenError(Exception):
    """Raised when a fixture's `expected` block is mutated at runtime.

    The contract is frozen by design; touching it is a harness violation.
    """

    def __init__(self, test_id: str):
        super().__init__(
            f"Test {test_id}: attempted to mutate the frozen `expected` block. "
            "Expected outcomes are the contract and must not be changed to "
            "accommodate implementation."
        )
        self.test_id = test_id
